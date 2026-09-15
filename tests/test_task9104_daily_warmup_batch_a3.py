from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    task9_required_completed_daily_candle_at,
)
from services.task9_daily_historical_warmup_retry import (
    Task9DailyWarmupRetryStore,
)


IST = ZoneInfo("Asia/Kolkata")
END_TIME = datetime(2026, 8, 14, 16, tzinfo=IST)
NIFTY_EXCHANGE = "NSE"
NIFTY_TOKEN = "99926000"


def _daily_response(required, *, count=55, include_required=True):
    last = required if include_required else required - timedelta(days=1)
    return {
        "status": True,
        "data": [
            [
                (last - timedelta(days=count - index - 1)).isoformat(),
                24000.0 + index,
                24002.0 + index,
                23998.0 + index,
                24001.0 + index,
                1000,
            ]
            for index in range(count)
        ],
    }


class _DailyClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_historical_data(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _CacheWriteFailure(HistoricalDataCache):
    def set(self, *args, **kwargs):
        raise OSError("temporary cache write failure")


def _service(
    *,
    client,
    cache,
    retry_path,
    clock,
    cooldown=None,
):
    return LiveMultiTimeframeData(
        client=client,
        cache=cache,
        provider_cooldown=cooldown,
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=(
            Task9DailyWarmupRetryStore(
                retry_path,
                time_function=lambda: clock[0],
            )
        ),
    )


def _assert_first_failed_attempt(result, client, retry_path, clock):
    assert result["refresh_outcome"] == "UNAVAILABLE"
    assert result["refresh_attempted"] is True
    assert result["provider_call_count"] == 1
    assert result["logical_attempt_count"] == 1
    assert result["cache_state_after"] == "UNAVAILABLE"
    assert result["warnings"] == (
        "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
    )
    assert len(client.calls) == 1

    state = Task9DailyWarmupRetryStore(
        retry_path,
        time_function=lambda: clock[0],
    ).status(
        exchange=NIFTY_EXCHANGE,
        symboltoken=NIFTY_TOKEN,
        required_identity=result["required_completed_candle_at"],
    )

    assert state["attempt_count"] == 1
    assert state["exhausted"] is False
    assert state["next_attempt_at_epoch_seconds"] == clock[0] + 300
    assert state["failure_category"]


@pytest.mark.parametrize(
    "provider_result",
    (
        pytest.param(TimeoutError("timeout"), id="timeout"),
        pytest.param(RuntimeError("ordinary provider failure"), id="ordinary-exception"),
        pytest.param({"status": True, "data": []}, id="empty-response"),
        pytest.param({"status": True, "data": "malformed"}, id="malformed-data"),
        pytest.param(None, id="non-object-response"),
    ),
)
def test_a3_provider_and_response_failures_consume_one_attempt(
    tmp_path,
    provider_result,
):
    clock = [100.0]
    retry_path = tmp_path / "retry.json"
    client = _DailyClient(provider_result)
    service = _service(
        client=client,
        cache=HistoricalDataCache(
            tmp_path / "cache.json",
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
    )

    result = service.ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    _assert_first_failed_attempt(
        result,
        client,
        retry_path,
        clock,
    )


def test_a3_insufficient_completed_history_consumes_one_attempt(tmp_path):
    clock = [100.0]
    retry_path = tmp_path / "retry.json"
    required = task9_required_completed_daily_candle_at(
        END_TIME,
        exchange=NIFTY_EXCHANGE,
    )
    client = _DailyClient(
        _daily_response(required, count=49),
    )
    service = _service(
        client=client,
        cache=HistoricalDataCache(
            tmp_path / "cache.json",
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
    )

    result = service.ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    _assert_first_failed_attempt(
        result,
        client,
        retry_path,
        clock,
    )


def test_a3_temporary_cache_write_failure_consumes_one_attempt(tmp_path):
    clock = [100.0]
    retry_path = tmp_path / "retry.json"
    required = task9_required_completed_daily_candle_at(
        END_TIME,
        exchange=NIFTY_EXCHANGE,
    )
    client = _DailyClient(
        _daily_response(
            required + timedelta(days=1),
            count=51,
        ),
    )
    service = _service(
        client=client,
        cache=_CacheWriteFailure(
            tmp_path / "cache.json",
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
    )

    result = service.ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    _assert_first_failed_attempt(
        result,
        client,
        retry_path,
        clock,
    )


def test_a3_retry_backoff_precedes_active_provider_cooldown(tmp_path):
    clock = [100.0]
    retry_path = tmp_path / "retry.json"
    cooldown_path = tmp_path / "cooldown.json"
    client = _DailyClient(TimeoutError("timeout"))
    cache_path = tmp_path / "cache.json"

    first = _service(
        client=client,
        cache=HistoricalDataCache(
            cache_path,
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
    ).ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )
    assert first["logical_attempt_count"] == 1

    cooldown = HistoricalProviderCooldown(
        cooldown_path,
        time_function=lambda: clock[0],
    )
    cooldown.record_rate_limit(
        reason="HISTORICAL-DATA_RATE_LIMITED",
        cooldown_seconds=900,
    )

    restarted = _service(
        client=client,
        cache=HistoricalDataCache(
            cache_path,
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
        cooldown=HistoricalProviderCooldown(
            cooldown_path,
            time_function=lambda: clock[0],
        ),
    )
    result = restarted.ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    assert result["refresh_outcome"] == "RETRY_BACKOFF_ACTIVE"
    assert result["provider_call_count"] == 0
    assert result["logical_attempt_count"] == 1
    assert len(client.calls) == 1


def test_a3_provider_cooldown_after_retry_boundary_consumes_no_attempt(
    tmp_path,
):
    clock = [100.0]
    retry_path = tmp_path / "retry.json"
    cooldown_path = tmp_path / "cooldown.json"
    cache_path = tmp_path / "cache.json"
    client = _DailyClient(TimeoutError("timeout"))

    first = _service(
        client=client,
        cache=HistoricalDataCache(
            cache_path,
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
    ).ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )
    assert first["next_attempt_at_epoch_seconds"] == 400.0

    cooldown = HistoricalProviderCooldown(
        cooldown_path,
        time_function=lambda: clock[0],
    )
    cooldown.record_rate_limit(
        reason="HISTORICAL-DATA_RATE_LIMITED",
        cooldown_seconds=900,
    )

    clock[0] = 400.0
    suppressed = _service(
        client=client,
        cache=HistoricalDataCache(
            cache_path,
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
        cooldown=HistoricalProviderCooldown(
            cooldown_path,
            time_function=lambda: clock[0],
        ),
    ).ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    assert suppressed["refresh_outcome"] == "PROVIDER_THROTTLED"
    assert suppressed["provider_call_count"] == 0
    assert suppressed["logical_attempt_count"] == 1
    assert len(client.calls) == 1

    state = Task9DailyWarmupRetryStore(
        retry_path,
        time_function=lambda: clock[0],
    ).status(
        exchange=NIFTY_EXCHANGE,
        symboltoken=NIFTY_TOKEN,
        required_identity=first["required_completed_candle_at"],
    )
    assert state["attempt_count"] == 1
    assert state["next_attempt_at_epoch_seconds"] == 400.0

    clock[0] = 1000.0
    permitted = _service(
        client=client,
        cache=HistoricalDataCache(
            cache_path,
            time_function=lambda: clock[0],
        ),
        retry_path=retry_path,
        clock=clock,
        cooldown=HistoricalProviderCooldown(
            cooldown_path,
            time_function=lambda: clock[0],
        ),
    ).ensure_daily_cache_coverage(
        NIFTY_EXCHANGE,
        NIFTY_TOKEN,
        end_time=END_TIME,
    )

    assert permitted["refresh_outcome"] == "UNAVAILABLE"
    assert permitted["provider_call_count"] == 1
    assert permitted["logical_attempt_count"] == 2
    assert len(client.calls) == 2

