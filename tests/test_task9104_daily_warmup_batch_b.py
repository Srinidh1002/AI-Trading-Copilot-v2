from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from services.historical_data_cache import HistoricalDataCache
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    task9_required_completed_daily_candle_at,
)
import services.market.task9_historical_websocket_composition as composition
from services.task9_daily_historical_warmup_retry import (
    Task9DailyWarmupRetryStore,
)


IST = ZoneInfo("Asia/Kolkata")


def _row(timestamp, *, close=24001.0):
    return [
        timestamp.isoformat(),
        close - 1.0,
        close + 1.0,
        close - 2.0,
        close,
        1000,
    ]


def _response(timestamps):
    return {
        "status": True,
        "data": [
            _row(timestamp, close=24001.0 + index)
            for index, timestamp in enumerate(timestamps)
        ],
    }


def _completed_timestamps(required, count):
    return tuple(
        required - timedelta(days=count - index - 1)
        for index in range(count)
    )


class _DailyClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_historical_data(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


@pytest.mark.parametrize(
    "hour,minute",
    (
        (9, 0),
        (15, 29),
        (15, 30),
        (15, 31),
        (16, 0),
        (23, 59),
    ),
)
@pytest.mark.parametrize("exchange", ("NSE", "BSE"))
def test_b_task9_daily_identity_is_prior_session_at_all_times(
    exchange,
    hour,
    minute,
):
    end_time = datetime(
        2026,
        8,
        14,
        hour,
        minute,
        tzinfo=IST,
    )

    assert task9_required_completed_daily_candle_at(
        end_time,
        exchange=exchange,
    ) == datetime(2026, 8, 13, tzinfo=IST)


@pytest.mark.parametrize(
    "end_time,expected",
    (
        (
            datetime(2026, 8, 15, 16, tzinfo=IST),
            datetime(2026, 8, 14, tzinfo=IST),
        ),
        (
            datetime(2026, 8, 16, 16, tzinfo=IST),
            datetime(2026, 8, 14, tzinfo=IST),
        ),
        (
            datetime(2026, 8, 17, 16, tzinfo=IST),
            datetime(2026, 8, 14, tzinfo=IST),
        ),
        (
            datetime(2026, 1, 26, 16, tzinfo=IST),
            datetime(2026, 1, 23, tzinfo=IST),
        ),
        (
            datetime(2026, 1, 27, 16, tzinfo=IST),
            datetime(2026, 1, 23, tzinfo=IST),
        ),
    ),
)
@pytest.mark.parametrize("exchange", ("NSE", "BSE"))
def test_b_task9_daily_identity_skips_weekends_and_holidays(
    exchange,
    end_time,
    expected,
):
    assert task9_required_completed_daily_candle_at(
        end_time,
        exchange=exchange,
    ) == expected


def test_b_task9_daily_identity_requires_timezone_aware_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        task9_required_completed_daily_candle_at(
            datetime(2026, 8, 14, 16),
            exchange="NSE",
        )


def test_b_daily_coverage_requires_50_unique_rows_and_exact_identity():
    required = datetime(2026, 8, 13, tzinfo=IST)
    unique_50 = _completed_timestamps(required, 50)

    assert LiveMultiTimeframeData._has_required_daily_coverage(
        _response(unique_50),
        required.isoformat(),
        50,
    )

    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        _response(unique_50[1:]),
        required.isoformat(),
        50,
    )

    missing_required = _completed_timestamps(
        required - timedelta(days=1),
        55,
    )
    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        _response(missing_required),
        required.isoformat(),
        50,
    )

    # A duplicate required row must not manufacture the fiftieth candle.
    duplicated_49 = unique_50[1:] + (required,)
    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        _response(duplicated_49),
        required.isoformat(),
        50,
    )


def test_b_daily_coverage_ignores_partial_and_future_rows_for_counting():
    required = datetime(2026, 8, 13, tzinfo=IST)
    completed_50 = _completed_timestamps(required, 50)
    partial_current = required + timedelta(days=1)
    future = required + timedelta(days=10)

    assert LiveMultiTimeframeData._has_required_daily_coverage(
        _response(completed_50 + (partial_current, future)),
        required.isoformat(),
        50,
    )

    completed_49 = completed_50[1:]
    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        _response(completed_49 + (partial_current, future)),
        required.isoformat(),
        50,
    )


def test_b_daily_coverage_rejects_unordered_completed_rows():
    required = datetime(2026, 8, 13, tzinfo=IST)
    values = [
        required - timedelta(days=offset)
        for offset in range(50)
    ]
    unordered = tuple(values[::2] + values[1::2])

    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        _response(unordered),
        required.isoformat(),
        50,
    )


@pytest.mark.parametrize(
    "response,required,minimum",
    (
        (None, "2026-08-13T00:00:00+05:30", 50),
        ({}, "2026-08-13T00:00:00+05:30", 50),
        ({"data": "bad"}, "2026-08-13T00:00:00+05:30", 50),
        ({"data": []}, "not-a-timestamp", 50),
        ({"data": []}, "2026-08-13T00:00:00+05:30", 0),
        ({"data": []}, "2026-08-13T00:00:00+05:30", True),
    ),
)
def test_b_daily_coverage_malformed_inputs_fail_closed(
    response,
    required,
    minimum,
):
    assert not LiveMultiTimeframeData._has_required_daily_coverage(
        response,
        required,
        minimum,
    )


def test_b_warmup_reports_required_identity_as_latest_completed(tmp_path):
    clock = [100.0]
    end_time = datetime(2026, 8, 14, 16, tzinfo=IST)
    required = task9_required_completed_daily_candle_at(
        end_time,
        exchange="NSE",
    )
    completed = _completed_timestamps(required, 50)
    current_partial = required + timedelta(days=1)
    client = _DailyClient(
        _response(completed + (current_partial,)),
    )
    service = LiveMultiTimeframeData(
        client=client,
        cache=HistoricalDataCache(
            tmp_path / "cache.json",
            time_function=lambda: clock[0],
        ),
        historical_request_gate=MagicMock(acquire=lambda: {}),
        task9_daily_warmup_retry_store=(
            Task9DailyWarmupRetryStore(
                tmp_path / "retry.json",
                time_function=lambda: clock[0],
            )
        ),
    )

    result = service.ensure_daily_cache_coverage(
        "NSE",
        "99926000",
        end_time=end_time,
    )

    assert result["refresh_outcome"] == "REFRESHED"
    assert result["required_completed_candle_at"] == required.isoformat()
    assert result["latest_completed_candle_at"] == required.isoformat()
    assert len(client.calls) == 1


class _CompositionCache:
    def __init__(self, daily_response):
        self.daily_response = daily_response

    def get_incremental_candidate(
        self,
        exchange,
        symboltoken,
        timeframe,
    ):
        response = (
            self.daily_response
            if timeframe == "1d"
            else {
                "status": True,
                "data": [
                    _row(
                        datetime(2026, 8, 14, 9, 15, tzinfo=IST),
                    )
                ],
            }
        )
        return {"response": response}


class _CompositionAggregator:
    def candles(self, **_kwargs):
        return ()


class _CompositionAdapter:
    def __init__(self):
        self.aggregator = _CompositionAggregator()

    def compose(self, **_kwargs):
        return SimpleNamespace(
            ready=True,
            source_composition=("HISTORICAL_CACHE",),
            failure_reason=None,
        )


def test_b_cache_only_composition_filters_partial_future_and_duplicates(
    tmp_path,
    monkeypatch,
):
    end_time = datetime(2026, 8, 14, 16, tzinfo=IST)
    required = task9_required_completed_daily_candle_at(
        end_time,
        exchange="NSE",
    )
    prior = required - timedelta(days=1)
    current_partial = required + timedelta(days=1)
    future = required + timedelta(days=2)
    response = {
        "status": True,
        "data": (
            _row(required, close=24001.0),
            _row(future, close=25000.0),
            _row(prior, close=23900.0),
            _row(required, close=24002.0),
            _row(current_partial, close=24500.0),
        ),
    }

    adapter = _CompositionAdapter()
    monkeypatch.setattr(
        composition,
        "Task9HistoricalWebsocketComposition",
        lambda **_kwargs: adapter,
    )
    factory = composition.build_task9_precomposed_timeframe_provider(
        live_stream_root=tmp_path,
        session_state_resolver=lambda **_kwargs: "REGULAR",
    )
    provider = factory(
        SimpleNamespace(
            cache=_CompositionCache(response),
        )
    )

    result = provider(
        exchange="NSE",
        symboltoken="99926000",
        end_time=end_time,
    )
    daily_rows = result["rows_by_timeframe"]["1d"]
    timestamps = tuple(
        datetime.fromisoformat(row[0]).astimezone(IST)
        for row in daily_rows
    )

    assert timestamps == (prior, required)
    assert len(daily_rows) == 2
    # Duplicate identity is deterministic: the last cached row wins.
    assert daily_rows[-1][4] == 24002.0
    assert all(timestamp <= required for timestamp in timestamps)

