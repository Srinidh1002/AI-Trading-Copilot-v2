from datetime import datetime, time, timedelta
import json
import hashlib
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    required_closed_candle_at,
    task9_required_completed_daily_candle_at,
)
from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.historical_request_gate import HistoricalRequestGate
from services.task9_daily_historical_warmup_retry import Task9DailyWarmupRetryStore
from services.market_session.policies import MarketSessionPolicy
from services.market_session.validator import validate_session_timestamp


def candle_data():
    return {
        "status": True,
        "data": [
            [
                "2026-07-10T09:15:00+05:30",
                24124.7,
                24187.9,
                24120.35,
                24162.7,
                0,
            ],
            [
                "2026-07-10T09:20:00+05:30",
                24162.7,
                24190.0,
                24150.0,
                24180.0,
                0,
            ],
        ],
    }


def make_cache():
    cache = MagicMock()

    cache.get.return_value = None

    return cache


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


def test_daily_cache_warmup_reuses_valid_cache_and_refreshes_missing_once(tmp_path):
    end_time = datetime(2026, 8, 14, 13, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    required = required_closed_candle_at("1d", end_time, exchange="NSE")
    cache = HistoricalDataCache(tmp_path / "daily-cache.json", time_function=lambda: 1.0)
    client = _DailyClient(_daily_response(required))
    cache.set("NSE", "99926000", "1d", _daily_response(required), requested_until=end_time.isoformat())
    service = LiveMultiTimeframeData(client=client, cache=cache)

    reused = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert reused["refresh_outcome"] == "REUSED"
    assert reused["provider_call_count"] == 0
    assert client.calls == []

    missing_cache = HistoricalDataCache(tmp_path / "missing-daily-cache.json", time_function=lambda: 1.0)
    missing_client = _DailyClient(_daily_response(required))
    missing_service = LiveMultiTimeframeData(client=missing_client, cache=missing_cache)
    refreshed = missing_service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    repeated = missing_service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)

    assert refreshed["refresh_outcome"] == "REFRESHED"
    assert refreshed["required_completed_candle_at"] == required.isoformat()
    assert repeated["refresh_outcome"] == "REUSED"
    assert len(missing_client.calls) == 1
    assert missing_client.calls[0]["interval"] == "ONE_DAY"


def test_daily_cache_warmup_rejects_insufficient_or_partial_daily_history(tmp_path):
    end_time = datetime(2026, 8, 14, 13, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    required = required_closed_candle_at("1d", end_time, exchange="BSE")
    # The current partial-day row leaves only 49 completed rows through the
    # required prior session and must not replace a valid cache authority.
    partial = _daily_response(required + timedelta(days=1), count=50)
    cache = HistoricalDataCache(tmp_path / "partial-daily-cache.json", time_function=lambda: 1.0)
    older = _daily_response(required, count=55)
    cache.set("BSE", "99919000", "1d", older, requested_until=end_time.isoformat())
    client = _DailyClient(partial)
    service = LiveMultiTimeframeData(client=client, cache=cache)

    result = service.ensure_daily_cache_coverage(
        "BSE", "99919000", end_time=end_time, minimum_completed_candles=56
    )

    assert result["refresh_outcome"] == "UNAVAILABLE"
    assert result["warnings"] == ("OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",)
    assert len(client.calls) == 1
    persisted = cache.get_incremental_candidate("BSE", "99919000", "1d")
    assert persisted["response"] == older


def test_daily_cache_warmup_uses_durable_bounded_retry_and_prior_session_identity(tmp_path):
    end_time = datetime(2026, 8, 14, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    clock = [1_000.0]
    retry = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: clock[0])
    client = _DailyClient(TimeoutError("timeout"))
    service = LiveMultiTimeframeData(
        client=client,
        cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]),
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=retry,
    )

    first = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    suppressed = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    clock[0] += 300
    second = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)

    assert first["logical_attempt_count"] == 1
    assert suppressed["refresh_outcome"] == "RETRY_BACKOFF_ACTIVE"
    assert second["logical_attempt_count"] == 2
    assert len(client.calls) == 2
    # Task 9 always consumes the prior session even after 15:30.
    assert first["required_completed_candle_at"] == "2026-08-13T00:00:00+05:30"


def test_daily_warmup_four_attempt_limit_survives_restart_and_resets_for_new_identity(tmp_path):
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    clock = [0.0]
    retry_path = tmp_path / "retry.json"
    cache_path = tmp_path / "cache.json"
    client = _DailyClient(TimeoutError("timeout"))
    def service():
        return LiveMultiTimeframeData(client=client, cache=HistoricalDataCache(cache_path, time_function=lambda: clock[0]), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]))
    value = service()
    for advance, expected in ((0, 1), (300, 2), (900, 3), (1800, 4)):
        clock[0] += advance
        result = value.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
        assert result["logical_attempt_count"] == expected
    assert value.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "ATTEMPT_BUDGET_EXHAUSTED"
    restarted = service()
    assert restarted.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["provider_call_count"] == 0
    next_day = datetime(2026, 8, 17, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert restarted.ensure_daily_cache_coverage("NSE", "99926000", end_time=next_day)["logical_attempt_count"] == 1
    assert len(client.calls) == 5


def test_daily_warmup_180_cycles_and_corrupt_retry_state_fail_safe(tmp_path):
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    clock = [0.0]
    retry_path = tmp_path / "retry.json"
    client = _DailyClient(TimeoutError("timeout"))
    service = LiveMultiTimeframeData(client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]))
    outcomes = []
    for _ in range(180):
        outcomes.append(service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"])
        clock[0] += 60
    assert len(client.calls) == 4
    assert outcomes.count("ATTEMPT_BUDGET_EXHAUSTED") > 0
    retry_path.write_text("not-json", encoding="utf-8")
    assert service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_STATE_INVALID"
    assert len(client.calls) == 4


@pytest.mark.parametrize("document", (
    "not-json", "null", "[]", "\"text\"", "0", "1.5", "true", "{}",
    {"version": 99, "entries": {}}, {"version": 1, "entries": []},
    {"version": 1, "entries": "bad"}, {"version": 1, "entries": None},
    {"version": 1, "entries": {"bad": []}},
    {"version": 1, "entries": {"bad": "text"}},
    {"version": 1, "entries": {"bad": None}},
    {"version": 1, "entries": {"bad": {"attempt_count": -1}}},
))
def test_daily_warmup_malformed_retry_documents_never_call_provider(tmp_path, document):
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    retry_path = tmp_path / "retry.json"
    payload = document if isinstance(document, str) else json.dumps(document)
    retry_path.write_text(payload, encoding="utf-8")
    client = _DailyClient(TimeoutError("must not call"))
    service = LiveMultiTimeframeData(
        client=client,
        cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: 1.0),
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: 1.0),
    )
    assert service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_STATE_INVALID"
    assert client.calls == []
    restarted = LiveMultiTimeframeData(
        client=client,
        cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: 1.0),
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: 1.0),
    )
    assert restarted.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_STATE_INVALID"
    assert client.calls == []
    assert retry_path.read_text(encoding="utf-8") == payload


def test_daily_warmup_active_provider_cooldown_precedes_retry_and_provider_call(tmp_path):
    clock = [100.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    cooldown = HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: clock[0])
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=900)
    retry = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: clock[0])
    client = _DailyClient(TimeoutError("must not call"))
    service = LiveMultiTimeframeData(
        client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]),
        provider_cooldown=cooldown, historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=retry,
    )
    result = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert result["refresh_outcome"] == "PROVIDER_THROTTLED"
    assert result["provider_call_count"] == 0
    assert client.calls == []
    assert retry.status(exchange="NSE", symboltoken="99926000", required_identity=result["required_completed_candle_at"]) is None


def test_daily_warmup_outbound_rate_limit_consumes_one_retry_and_persists_cooldown(tmp_path):
    from services.broker.market_data_control import BrokerMarketDataRequestError

    clock = [100.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    client = _DailyClient(BrokerMarketDataRequestError("historical-data", 1, "rate_limited", "sanitized"))
    client.request_controller = type("Controller", (), {"rate_limit_cooldown_seconds": 900})()
    cooldown = HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: clock[0])
    retry = Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: clock[0])
    service = LiveMultiTimeframeData(
        client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]),
        provider_cooldown=cooldown, historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=retry,
    )
    first = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    second = service.ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    state = retry.status(exchange="NSE", symboltoken="99926000", required_identity=first["required_completed_candle_at"])
    assert first["provider_call_count"] == 1
    assert second["provider_call_count"] == 0
    assert len(client.calls) == 1
    assert state["attempt_count"] == 1
    assert state["next_attempt_at_epoch_seconds"] == 1000.0
    assert cooldown.active()["expires_at_epoch_seconds"] == 1000.0


def test_daily_warmup_public_service_two_market_180_cycle_budget(tmp_path):
    clock = [0.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    retry_path = tmp_path / "retry.json"
    cache_path = tmp_path / "cache.json"
    clients = {"NSE": _DailyClient(TimeoutError("nifty")), "BSE": _DailyClient(TimeoutError("sensex"))}
    def service(exchange):
        return LiveMultiTimeframeData(
            client=clients[exchange], cache=HistoricalDataCache(cache_path, time_function=lambda: clock[0]),
            historical_request_gate=MagicMock(acquire=lambda: {}),
            task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]),
        )
    services = {"NSE": service("NSE"), "BSE": service("BSE")}
    records = {"NSE": [], "BSE": []}
    for _ in range(180):
        records["NSE"].append(services["NSE"].ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time))
        records["BSE"].append(services["BSE"].ensure_daily_cache_coverage("BSE", "99919000", end_time=end_time))
        clock[0] += 60
    assert len(clients["NSE"].calls) == len(clients["BSE"].calls) == 4
    assert sum(len(client.calls) for client in clients.values()) == 8
    assert all(sum(result["provider_call_count"] == 0 for result in values) == 176 for values in records.values())
    assert all(values[-1]["refresh_outcome"] == "ATTEMPT_BUDGET_EXHAUSTED" for values in records.values())
    assert Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]).status(exchange="NSE", symboltoken="99926000", required_identity=records["NSE"][-1]["required_completed_candle_at"])["exhausted"]
    assert Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]).status(exchange="BSE", symboltoken="99919000", required_identity=records["BSE"][-1]["required_completed_candle_at"])["exhausted"]


def test_daily_warmup_restart_preserves_first_and_later_backoff_boundaries(tmp_path):
    clock = [0.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    client = _DailyClient(TimeoutError("timeout"))
    def service():
        return LiveMultiTimeframeData(client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(tmp_path / "retry.json", time_function=lambda: clock[0]))
    first = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_BACKOFF_ACTIVE"
    clock[0] = first["next_attempt_at_epoch_seconds"]
    second = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert second["logical_attempt_count"] == 2
    clock[0] = second["next_attempt_at_epoch_seconds"] - 1
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_BACKOFF_ACTIVE"
    clock[0] += 1
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["logical_attempt_count"] == 3
    assert len(client.calls) == 3


def test_a2b_no_sleep_for_all_nonblocking_daily_warmup_paths(tmp_path):
    def unexpected_sleep(_seconds):
        raise AssertionError("unexpected sleep")
    clock = [0.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    path = tmp_path / "retry.json"
    gate = HistoricalRequestGate(tmp_path / "gate.json", time_function=lambda: clock[0], sleep_function=unexpected_sleep)
    client = _DailyClient(TimeoutError("must not call"))
    def service(*, cooldown=None, cache=None):
        return LiveMultiTimeframeData(client=client, cache=cache or HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]), provider_cooldown=cooldown, historical_request_gate=gate, task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(path, time_function=lambda: clock[0]))
    first = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_BACKOFF_ACTIVE"
    for advance in (300, 900, 1800):
        clock[0] += advance; service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "ATTEMPT_BUDGET_EXHAUSTED"
    path.write_text("not-json", encoding="utf-8")
    assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "RETRY_STATE_INVALID"
    path.unlink()
    cooldown = HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: clock[0]); cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=900)
    assert service(cooldown=cooldown).ensure_daily_cache_coverage("BSE", "99919000", end_time=end_time)["refresh_outcome"] == "PROVIDER_THROTTLED"
    fresh_cache = HistoricalDataCache(tmp_path / "fresh.json", time_function=lambda: clock[0]); required = required_closed_candle_at("1d", end_time, exchange="NSE"); fresh_cache.set("NSE", "99926000", "1d", _daily_response(required), requested_until=end_time.isoformat())
    assert service(cache=fresh_cache).ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["refresh_outcome"] == "REUSED"
    assert len(client.calls) == 4 and first["logical_attempt_count"] == 1


def test_a2b_restart_after_exhaustion_keeps_same_identity_suppressed(tmp_path):
    clock = [0.0]; end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata")); client = _DailyClient(TimeoutError("timeout")); retry_path = tmp_path / "retry.json"
    def service(): return LiveMultiTimeframeData(client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]))
    for advance in (0, 300, 900, 1800): clock[0] += advance; service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    identity = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)["required_completed_candle_at"]; document = retry_path.read_text(encoding="utf-8")
    for later in (60, 3600, 8 * 3600):
        clock[0] += later; result = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
        assert result["refresh_outcome"] == "ATTEMPT_BUDGET_EXHAUSTED"
    assert len(client.calls) == 4
    assert Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]).status(exchange="NSE", symboltoken="99926000", required_identity=identity)["attempt_count"] == 4
    assert retry_path.read_text(encoding="utf-8") == document


def test_a2b_restart_after_success_reuses_durable_daily_cache(tmp_path):
    end_time = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata")); required = task9_required_completed_daily_candle_at(end_time, exchange="NSE")
    response = _daily_response(required + timedelta(days=1), count=51); cache_path = tmp_path / "cache.json"; retry_path = tmp_path / "retry.json"; first_client = _DailyClient(response)
    first = LiveMultiTimeframeData(client=first_client, cache=HistoricalDataCache(cache_path, time_function=lambda: 1.0), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: 1.0)).ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    digest = hashlib.sha256(cache_path.read_bytes()).hexdigest(); second_client = _DailyClient(TimeoutError("must not call"))
    second = LiveMultiTimeframeData(client=second_client, cache=HistoricalDataCache(cache_path, time_function=lambda: 1.0), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: 1.0)).ensure_daily_cache_coverage("NSE", "99926000", end_time=end_time)
    assert first["refresh_outcome"] == "REFRESHED" and len(first_client.calls) == 1
    assert second["refresh_outcome"] == "REUSED" and second_client.calls == []
    assert hashlib.sha256(cache_path.read_bytes()).hexdigest() == digest
    assert first["required_completed_candle_at"] == required.isoformat()
    assert not retry_path.exists() or Task9DailyWarmupRetryStore(retry_path, time_function=lambda: 1.0).status(exchange="NSE", symboltoken="99926000", required_identity=required.isoformat()) is None


def test_a2b_service_identity_reset_is_by_completed_session_identity(tmp_path):
    clock = [0.0]; client = _DailyClient(TimeoutError("timeout")); retry_path = tmp_path / "retry.json"; a = datetime(2026, 8, 14, 16, tzinfo=ZoneInfo("Asia/Kolkata")); b = datetime(2026, 8, 17, 16, tzinfo=ZoneInfo("Asia/Kolkata"))
    def service(): return LiveMultiTimeframeData(client=client, cache=HistoricalDataCache(tmp_path / "cache.json", time_function=lambda: clock[0]), historical_request_gate=MagicMock(acquire=lambda: {}), task9_daily_warmup_retry_store=Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]))
    for advance in (0, 300, 900, 1800): clock[0] += advance; service().ensure_daily_cache_coverage("NSE", "99926000", end_time=a)
    clock[0] += 3600; assert service().ensure_daily_cache_coverage("NSE", "99926000", end_time=a)["refresh_outcome"] == "ATTEMPT_BUDGET_EXHAUSTED"
    fresh = service().ensure_daily_cache_coverage("NSE", "99926000", end_time=b)
    assert fresh["logical_attempt_count"] == 1 and len(client.calls) == 5
    store = Task9DailyWarmupRetryStore(retry_path, time_function=lambda: clock[0]); assert store.status(exchange="NSE", symboltoken="99926000", required_identity="2026-08-13T00:00:00+05:30")["exhausted"]


def test_a2b_public_service_market_and_identity_authorities_are_independent(
    tmp_path,
):
    clock = [0.0]
    end = datetime(
        2026,
        8,
        14,
        16,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    retry_path = tmp_path / "retry.json"
    cache_path = tmp_path / "cache.json"

    nifty = _DailyClient(TimeoutError("nifty"))
    sensex_required = task9_required_completed_daily_candle_at(
        end,
        exchange="BSE",
    )
    sensex = _DailyClient(
        _daily_response(
            sensex_required + timedelta(days=1),
            count=51,
        ),
    )

    def service(client):
        return LiveMultiTimeframeData(
            client=client,
            cache=HistoricalDataCache(
                cache_path,
                time_function=lambda: clock[0],
            ),
            historical_request_gate=MagicMock(
                acquire=lambda: {},
            ),
            task9_daily_warmup_retry_store=(
                Task9DailyWarmupRetryStore(
                    retry_path,
                    time_function=lambda: clock[0],
                )
            ),
        )

    # Exhaust the genuine NIFTY authority.
    nifty_result = None
    for advance in (0, 300, 900, 1800):
        clock[0] += advance
        nifty_result = service(
            nifty,
        ).ensure_daily_cache_coverage(
            "NSE",
            "99926000",
            end_time=end,
        )

    assert nifty_result is not None
    original_identity = nifty_result[
        "required_completed_candle_at"
    ]

    # Warm the genuine SENSEX authority successfully.
    sensex_result = service(
        sensex,
    ).ensure_daily_cache_coverage(
        "BSE",
        "99919000",
        end_time=end,
    )

    store = Task9DailyWarmupRetryStore(
        retry_path,
        time_function=lambda: clock[0],
    )

    assert sensex_result["refresh_outcome"] == "REFRESHED"
    assert len(nifty.calls) == 4
    assert len(sensex.calls) == 1
    assert store.status(
        exchange="NSE",
        symboltoken="99926000",
        required_identity=original_identity,
    )["exhausted"]
    assert store.status(
        exchange="BSE",
        symboltoken="99919000",
        required_identity=sensex_result[
            "required_completed_candle_at"
        ],
    ) is None

    # SENSEX success must not clear or unblock NIFTY.
    exhausted_again = service(
        nifty,
    ).ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=end,
    )
    assert (
        exhausted_again["refresh_outcome"]
        == "ATTEMPT_BUDGET_EXHAUSTED"
    )
    assert len(nifty.calls) == 4

    # BSE:SENSEX cache must not satisfy NSE:SENSEX-token.
    nse_with_sensex_token = _DailyClient(
        TimeoutError("cross NSE/SENSEX token"),
    )
    nse_cross_result = service(
        nse_with_sensex_token,
    ).ensure_daily_cache_coverage(
        "NSE",
        "99919000",
        end_time=end,
    )

    assert nse_cross_result["refresh_outcome"] != "REUSED"
    assert nse_cross_result["provider_call_count"] == 1
    assert len(nse_with_sensex_token.calls) == 1
    assert store.status(
        exchange="NSE",
        symboltoken="99919000",
        required_identity=nse_cross_result[
            "required_completed_candle_at"
        ],
    )["attempt_count"] == 1

    # NSE:NIFTY cache/retry state must not satisfy BSE:NIFTY-token.
    bse_with_nifty_token = _DailyClient(
        TimeoutError("cross BSE/NIFTY token"),
    )
    bse_cross_result = service(
        bse_with_nifty_token,
    ).ensure_daily_cache_coverage(
        "BSE",
        "99926000",
        end_time=end,
    )

    assert bse_cross_result["refresh_outcome"] != "REUSED"
    assert bse_cross_result["provider_call_count"] == 1
    assert len(bse_with_nifty_token.calls) == 1
    assert store.status(
        exchange="BSE",
        symboltoken="99926000",
        required_identity=bse_cross_result[
            "required_completed_candle_at"
        ],
    )["attempt_count"] == 1

    # A new required completed-session identity must not reuse the
    # exhausted budget belonging to the original identity.
    next_end = datetime(
        2026,
        8,
        17,
        16,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    next_identity_client = _DailyClient(
        TimeoutError("new completed-session identity"),
    )
    next_identity_result = service(
        next_identity_client,
    ).ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=next_end,
    )

    assert (
        next_identity_result["required_completed_candle_at"]
        != original_identity
    )
    assert next_identity_result["refresh_outcome"] != "REUSED"
    assert next_identity_result["provider_call_count"] == 1
    assert next_identity_result["logical_attempt_count"] == 1
    assert len(next_identity_client.calls) == 1

    refreshed_store = Task9DailyWarmupRetryStore(
        retry_path,
        time_function=lambda: clock[0],
    )

    # Original authority remains exhausted and auditable.
    assert refreshed_store.status(
        exchange="NSE",
        symboltoken="99926000",
        required_identity=original_identity,
    )["exhausted"]

    # New identity has its own attempt budget.
    assert refreshed_store.status(
        exchange="NSE",
        symboltoken="99926000",
        required_identity=next_identity_result[
            "required_completed_candle_at"
        ],
    )["attempt_count"] == 1

    # The only valid durable cache belongs to BSE:SENSEX.
    cache = HistoricalDataCache(
        cache_path,
        time_function=lambda: clock[0],
    )
    assert cache.get(
        "BSE",
        "99919000",
        "1d",
        max_age_seconds=10**9,
    ) is not None
    assert cache.get(
        "NSE",
        "99919000",
        "1d",
        max_age_seconds=10**9,
    ) is None
    assert cache.get(
        "BSE",
        "99926000",
        "1d",
        max_age_seconds=10**9,
    ) is None


@pytest.mark.parametrize(
    ("exchange", "expected_start"),
    (
        ("NSE", time(15, 25)),
        ("BSE", time(15, 25)),
        ("NFO", time(15, 35)),
        ("BFO", time(15, 35)),
    ),
)
def test_after_hours_closed_candle_uses_exchange_historical_close(
    exchange,
    expected_start,
):
    result = required_closed_candle_at(
        "5m",
        datetime(2026, 7, 10, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange=exchange,
    )

    assert result.time() == expected_start


def test_historical_intraday_and_previous_session_boundaries_remain_exchange_aware():
    assert required_closed_candle_at(
        "5m",
        datetime(2026, 7, 10, 10, 17, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange="NSE",
    ).time() == time(10, 10)
    assert required_closed_candle_at(
        "5m",
        datetime(2026, 1, 26, 10, 17, tzinfo=ZoneInfo("Asia/Kolkata")),
        exchange="NSE",
    ) == datetime(2026, 1, 23, 15, 25, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_unknown_historical_exchange_fails_closed():
    with pytest.raises(ValueError, match="unsupported historical candle exchange"):
        required_closed_candle_at(
            "5m",
            datetime(2026, 7, 10, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
            exchange="UNKNOWN",
        )


def test_task9_execution_session_policy_remains_fno_authority():
    policy = MarketSessionPolicy()
    assert policy.new_entry_cutoff == time(15, 20)
    assert policy.regular_close == time(15, 40)

    result = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=datetime(2026, 7, 10, 15, 35, tzinfo=ZoneInfo("Asia/Kolkata")),
        evaluated_at=datetime(2026, 7, 10, 15, 35, tzinfo=ZoneInfo("Asia/Kolkata")),
        validation_mode="STRICT_EXECUTION",
        id_factory=lambda: "historical-session-separation",
    )
    assert result.session_state == "REGULAR"

    post_close = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=datetime(2026, 7, 10, 15, 41, tzinfo=ZoneInfo("Asia/Kolkata")),
        evaluated_at=datetime(2026, 7, 10, 15, 41, tzinfo=ZoneInfo("Asia/Kolkata")),
        validation_mode="STRICT_EXECUTION",
        id_factory=lambda: "historical-session-separation-post-close",
    )
    assert post_close.session_state == "POST_CLOSE"


def test_fetch_single_timeframe():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    assert service.cache is cache
    mock_client.get_historical_data.assert_not_called()

    result = service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert len(result) == 2

    assert list(result.columns) == [
        "timestamp",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 1
    )

    cache.set.assert_called_once()


def test_fetch_all_timeframes():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    result = service.fetch_all(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    assert set(result.keys()) == {
        "5m",
        "15m",
        "1h",
        "1d",
    }

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 4
    )

    assert (
        cache.set.call_count
        == 4
    )


def test_fresh_cache_avoids_broker_request():

    mock_client = MagicMock()

    cache = MagicMock()

    cache.get.return_value = (
        candle_data()
    )

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    result = service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert len(result) == 2

    mock_client.get_historical_data.assert_not_called()

    cache.set.assert_not_called()


def test_cache_disabled_always_uses_broker():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = (
        candle_data()
    )

    cache = MagicMock()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
        cache_enabled=False,
    )

    service.fetch_timeframe(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    cache.get.assert_not_called()

    cache.set.assert_not_called()

    assert (
        mock_client
        .get_historical_data
        .call_count
        == 1
    )


def test_invalid_timeframe():

    mock_client = MagicMock()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=make_cache(),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported timeframe",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="2m",
        )


def test_empty_api_data_is_not_cached():

    mock_client = MagicMock()

    mock_client.get_historical_data.return_value = {
        "status": True,
        "data": [],
    }

    cache = make_cache()

    service = LiveMultiTimeframeData(
        client=mock_client,
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="No candle data returned",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
        )

    cache.set.assert_not_called()


class MetadataCache:
    def __init__(
        self,
        result=None,
    ):
        self.result = result
        self.set_calls = []

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
    ):
        return self.result

    def set(
        self,
        exchange,
        symboltoken,
        timeframe,
        response,
        *,
        source,
        requested_until=None,
    ):
        self.set_calls.append(
            {
                "exchange": exchange,
                "symboltoken": symboltoken,
                "timeframe": timeframe,
                "response": response,
                "source": source,
            }
        )

        return response


class ClosedCoverageMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.required_closed_at = None

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
        required_closed_at=None,
    ):
        self.required_closed_at = required_closed_at
        return self.result


class KwargsMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.reader_kwargs = None

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        **kwargs,
    ):
        self.reader_kwargs = kwargs
        return self.result


class InternalTypeErrorMetadataCache(MetadataCache):
    def __init__(self, result=None):
        super().__init__(result=result)
        self.calls = 0

    def get_with_metadata(
        self,
        exchange,
        symboltoken,
        timeframe,
        *,
        max_age_seconds,
        required_until=None,
        required_closed_at=None,
    ):
        self.calls += 1
        raise TypeError("cache implementation failure")


def test_capture_metadata_preserves_persistent_cache_provenance(
    monkeypatch,
):
    cached = candle_data()

    cache = MetadataCache(
        result={
            "response": cached,
            "metadata": {
                "cache_status": "HIT",
                "cache_source": (
                    "ANGEL_ONE_HISTORICAL"
                ),
                "cache_key": (
                    "NSE:99926000:5m"
                ),
                "cached_at_epoch_seconds": (
                    1000.0
                ),
                "read_at_epoch_seconds": (
                    1060.0
                ),
                "age_seconds": 60.0,
                "max_age_seconds": 240.0,
                "expires_at_epoch_seconds": (
                    1240.0
                ),
                "expired": False,
            },
        }
    )

    client = MagicMock()

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result[
        "cache_metadata"
    ][
        "5m"
    ]

    assert metadata["cache_status"] == "HIT"
    assert metadata["age_seconds"] == 60.0

    assert (
        metadata["cache_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["provider_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["cache_write_status"]
        == "NOT_REQUIRED"
    )

    client.get_historical_data.assert_not_called()
    assert cache.set_calls == []


def test_live_capture_reports_cache_miss_and_write(
    monkeypatch,
):
    client = MagicMock()

    client.get_historical_data.return_value = (
        candle_data()
    )

    cache = MetadataCache(
        result=None
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result[
        "cache_metadata"
    ][
        "5m"
    ]

    assert metadata["cache_status"] == "MISS"

    assert (
        metadata["provider_source"]
        == "ANGEL_ONE_HISTORICAL"
    )

    assert (
        metadata["cache_write_status"]
        == "WRITTEN"
    )

    assert metadata["age_seconds"] == 0.0
    assert metadata["expired"] is False

    assert len(cache.set_calls) == 1

    assert (
        cache.set_calls[0]["source"]
        == "ANGEL_ONE_HISTORICAL"
    )


def test_invalid_live_candles_are_not_persisted():
    client = MagicMock()

    client.get_historical_data.return_value = {
        "status": True,
        "data": [
            [
                "2026-07-10T09:15:00",
                100,
                101,
                99,
                100,
                10,
            ]
        ],
    }

    cache = MetadataCache(
        result=None
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        service.fetch_timeframe(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
            end_time=datetime(
                2026,
                7,
                10,
                15,
                30,
            ),
        )

    assert cache.set_calls == []


def test_legacy_metadata_cache_uses_naive_end_time_contract():
    cache = MetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30),
    )

    assert len(cache.set_calls) == 1


def test_legacy_metadata_cache_uses_aware_end_time_contract():
    cache = MetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert len(cache.set_calls) == 1


def test_closed_coverage_cache_receives_required_closed_at():
    cache = ClosedCoverageMetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert cache.required_closed_at == "2026-07-10T15:25:00+05:30"


def test_kwargs_metadata_cache_receives_required_closed_at():
    cache = KwargsMetadataCache()
    client = MagicMock()
    client.get_historical_data.return_value = candle_data()

    service = LiveMultiTimeframeData(client=client, cache=cache)

    service.fetch_timeframe_raw(
        exchange="NSE",
        symboltoken="99926000",
        timeframe="5m",
        end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert cache.reader_kwargs["required_closed_at"] == "2026-07-10T15:25:00+05:30"


def test_internal_cache_type_error_is_not_retried_as_legacy_api():
    cache = InternalTypeErrorMetadataCache()
    service = LiveMultiTimeframeData(client=MagicMock(), cache=cache)

    with pytest.raises(TypeError, match="cache implementation failure"):
        service.fetch_timeframe_raw(
            exchange="NSE",
            symboltoken="99926000",
            timeframe="5m",
            end_time=datetime(2026, 7, 10, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
        )

    assert cache.calls == 1


def test_mock_cache_cannot_create_control_files_from_a_mock_file_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache = MagicMock()
    service = LiveMultiTimeframeData(client=MagicMock(), cache=cache)
    assert service.provider_cooldown is None
    assert service.historical_request_gate is None
    assert not (tmp_path / "MagicMock").exists()


def test_live_capture_retains_historical_rate_limit_reason(
    monkeypatch,
):
    from services.broker.market_data_control import (
        BrokerMarketDataRequestError,
    )

    client = MagicMock()
    client.get_historical_data.side_effect = (
        BrokerMarketDataRequestError(
            "historical-data",
            1,
            "rate_limited",
            "sanitized provider failure",
        )
    )

    service = LiveMultiTimeframeData(
        client=client,
        cache=make_cache(),
    )

    monkeypatch.setattr(
        "services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG",
        {
            "5m": {
                "interval": "FIVE_MINUTE",
                "lookback_days": 3,
            }
        },
    )

    result = service.fetch_all_with_capture(
        exchange="NSE",
        symboltoken="99926000",
        end_time=datetime(
            2026,
            7,
            10,
            15,
            30,
        ),
    )

    metadata = result["cache_metadata"]["5m"]

    assert result["rows_by_timeframe"]["5m"] == ()
    assert metadata["captured"] is False
    assert (
        metadata["failure_reason"]
        == "HISTORICAL-DATA_RATE_LIMITED"
    )
    assert metadata["provider_throttled"] is True


def test_task9104_incremental_daily_tail_validates_after_merge(tmp_path):
    """A short valid tail must be merged with deep cached history before coverage validation."""
    end_time = datetime(
        2026,
        8,
        25,
        13,
        15,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    required = task9_required_completed_daily_candle_at(
        end_time,
        exchange="NSE",
    )

    # Reproduce the Aug-25 live condition:
    # deep durable history exists but ends well before the required session.
    stale_last = required - timedelta(days=14)
    cached_response = _daily_response(
        stale_last,
        count=365,
    )

    # Only the missing tail is returned by the provider.  Fifteen rows are
    # intentionally far below minimum_completed_candles=50, so validating
    # this response before merging would incorrectly fail.
    incremental_tail = _daily_response(
        required,
        count=15,
    )

    cache = HistoricalDataCache(
        tmp_path / "incremental-daily-cache.json",
        time_function=lambda: 1.0,
    )
    cache.set(
        "NSE",
        "99926000",
        "1d",
        cached_response,
        requested_until=end_time.isoformat(),
    )

    client = _DailyClient(incremental_tail)
    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    result = service.ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=end_time,
        minimum_completed_candles=50,
    )

    assert result["refresh_outcome"] == "REFRESHED"
    assert result["provider_call_count"] == 1
    assert result["required_completed_candle_at"] == required.isoformat()
    assert len(client.calls) == 1
    assert client.calls[0]["interval"] == "ONE_DAY"

    persisted = cache.get_incremental_candidate(
        "NSE",
        "99926000",
        "1d",
    )
    rows = persisted["response"]["data"]

    # 365 cached calendar rows + 15 tail rows with one overlapping boundary row.
    assert len(rows) == 379
    assert rows[0] == cached_response["data"][0]
    assert rows[-1][0] == required.isoformat()


def test_task9104_incremental_daily_tail_missing_required_identity_fails_closed(
    tmp_path,
):
    """Merge must still fail when the exact required completed daily candle is absent."""
    end_time = datetime(
        2026,
        8,
        25,
        13,
        15,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    required = task9_required_completed_daily_candle_at(
        end_time,
        exchange="BSE",
    )

    stale_last = required - timedelta(days=14)
    cached_response = _daily_response(
        stale_last,
        count=365,
    )

    # Tail approaches the required session but deliberately stops one day
    # before it. Deep history alone must never satisfy exact-identity coverage.
    incomplete_tail = _daily_response(
        required,
        count=14,
        include_required=False,
    )

    cache = HistoricalDataCache(
        tmp_path / "incremental-daily-missing-required.json",
        time_function=lambda: 1.0,
    )
    cache.set(
        "BSE",
        "99919000",
        "1d",
        cached_response,
        requested_until=end_time.isoformat(),
    )

    client = _DailyClient(incomplete_tail)
    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
    )

    result = service.ensure_daily_cache_coverage(
        "BSE",
        "99919000",
        end_time=end_time,
        minimum_completed_candles=50,
    )

    assert result["refresh_outcome"] == "UNAVAILABLE"
    assert result["warnings"] == (
        "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
    )
    assert result["provider_call_count"] == 1

    # A failed incremental refresh must not replace the durable authority.
    persisted = cache.get_incremental_candidate(
        "BSE",
        "99919000",
        "1d",
    )
    assert persisted["response"] == cached_response
