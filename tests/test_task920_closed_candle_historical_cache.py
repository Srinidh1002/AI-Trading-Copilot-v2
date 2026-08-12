from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from services.broker.market_data_control import BrokerMarketDataRequestError
from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.market.live_multi_timeframe_data import (
    LiveMultiTimeframeData,
    required_closed_candle_at,
)


IST = ZoneInfo("Asia/Kolkata")
INTERVALS = {
    "FIVE_MINUTE": "5m",
    "FIFTEEN_MINUTE": "15m",
    "ONE_HOUR": "1h",
    "ONE_DAY": "1d",
}


def _at(value):
    return datetime.fromisoformat(value).replace(tzinfo=IST)


def _response(last_candle_start):
    return {
        "status": True,
        "data": [[last_candle_start.isoformat(), 100, 101, 99, 100, 10]],
    }


class Gate:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1
        return {"wait_seconds": 0.0}


def _provider_response(**kwargs):
    end_time = datetime.strptime(
        kwargs["todate"],
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=IST)
    timeframe = INTERVALS[kwargs["interval"]]
    return _response(
        required_closed_candle_at(
            timeframe,
            end_time,
            exchange=kwargs["exchange"],
        )
    )


def _service(tmp_path, *, now):
    client = MagicMock()
    client.request_controller = SimpleNamespace(rate_limit_cooldown_seconds=20.0)
    client.get_historical_data.side_effect = _provider_response
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: now[0])
    cooldown = HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: now[0])
    gate = Gate()
    return (
        LiveMultiTimeframeData(
            client=client,
            cache=cache,
            provider_cooldown=cooldown,
            historical_request_gate=gate,
        ),
        client,
        cache,
        cooldown,
        gate,
    )


@pytest.mark.parametrize(
    ("timeframe", "observed_at", "expected"),
    (
        ("5m", "2026-07-10T10:17:00", "2026-07-10T10:10:00+05:30"),
        ("5m", "2026-07-10T10:20:00", "2026-07-10T10:15:00+05:30"),
        ("15m", "2026-07-10T10:17:00", "2026-07-10T10:00:00+05:30"),
        ("1h", "2026-07-10T10:17:00", "2026-07-10T09:00:00+05:30"),
        ("1d", "2026-07-10T10:17:00", "2026-07-09T00:00:00+05:30"),
        ("1d", "2026-07-10T15:40:00", "2026-07-10T00:00:00+05:30"),
        ("5m", "2026-07-10T09:00:00", "2026-07-09T15:25:00+05:30"),
        ("5m", "2026-07-11T10:17:00", "2026-07-10T15:25:00+05:30"),
        ("1d", "2026-01-26T10:17:00", "2026-01-23T00:00:00+05:30"),
    ),
)
def test_required_closed_candle_boundary_uses_start_timestamps(
    timeframe,
    observed_at,
    expected,
):
    assert required_closed_candle_at(timeframe, _at(observed_at)) == _at(expected)


def test_closed_coverage_reuses_expired_wall_clock_cache_entry(tmp_path):
    now = [1000.0]
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: now[0])
    required = _at("2026-07-10T10:10:00")
    cache.set("NSE", "99926000", "5m", _response(required))
    now[0] += 10000.0

    result = cache.get_with_metadata(
        "NSE", "99926000", "5m", max_age_seconds=240, required_closed_at=required.isoformat()
    )

    assert result is not None
    assert result["metadata"]["age_seconds"] > 240


def test_closed_coverage_fails_when_required_candle_advances(tmp_path):
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: 1000.0)
    cache.set("NSE", "99926000", "5m", _response(_at("2026-07-10T10:10:00")))

    assert cache.get(
        "NSE", "99926000", "5m", max_age_seconds=240,
        required_closed_at=_at("2026-07-10T10:15:00").isoformat(),
    ) is None


def test_requested_until_cannot_replace_actual_closed_candle_coverage(tmp_path):
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: 1000.0)
    cache.set(
        "NSE", "99926000", "5m", _response(_at("2026-07-10T10:10:00")),
        requested_until=_at("2026-07-10T11:00:00").isoformat(),
    )

    assert cache.get(
        "NSE", "99926000", "5m", max_age_seconds=240,
        required_closed_at=_at("2026-07-10T10:15:00").isoformat(),
    ) is None


def test_old_schema_entry_without_coverage_metadata_uses_response_rows(tmp_path):
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: 1000.0)
    required = _at("2026-07-10T10:10:00")
    cache.set("NSE", "99926000", "5m", _response(required))

    assert cache.get(
        "NSE", "99926000", "5m", max_age_seconds=240,
        required_closed_at=required.isoformat(),
    ) is not None


@pytest.mark.parametrize(
    "rows",
    (
        [["2026-07-10T10:10:00", 100, 101, 99, 100, 10]],
        [
            ["2026-07-10T10:10:00+05:30", 100, 101, 99, 100, 10],
            ["2026-07-10T10:05:00+05:30", 100, 101, 99, 100, 10],
        ],
        [["not-a-timestamp", 100, 101, 99, 100, 10]],
    ),
)
def test_malformed_closed_coverage_rows_fail_closed(tmp_path, rows):
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: 1000.0)
    cache.set("NSE", "99926000", "5m", {"status": True, "data": rows})

    assert cache.get(
        "NSE", "99926000", "5m", max_age_seconds=240,
        required_closed_at=_at("2026-07-10T10:10:00").isoformat(),
    ) is None


def test_equivalent_capture_before_next_close_uses_only_cache(tmp_path):
    now = [1000.0]
    service, client, _, _, gate = _service(tmp_path, now=now)
    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:18:00"))

    assert client.get_historical_data.call_count - before == 0
    assert gate.calls == 4


def test_next_five_minute_close_refreshes_only_five_minute(tmp_path):
    now = [1000.0]
    service, client, _, _, _ = _service(tmp_path, now=now)
    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:20:00"))

    calls = client.get_historical_data.call_args_list[before:]
    assert len(calls) == 1
    assert calls[0].kwargs["interval"] == "FIVE_MINUTE"


def test_fifteen_minute_boundary_refreshes_five_and_fifteen_only(tmp_path):
    now = [1000.0]
    service, client, _, _, _ = _service(tmp_path, now=now)
    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:30:00"))

    assert {call.kwargs["interval"] for call in client.get_historical_data.call_args_list[before:]} == {
        "FIVE_MINUTE", "FIFTEEN_MINUTE"
    }


def test_hour_boundary_refreshes_all_intraday_timeframes_not_daily(tmp_path):
    now = [1000.0]
    service, client, _, _, _ = _service(tmp_path, now=now)
    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    service.fetch_all_with_capture("NSE", "99926000", end_time=_at("2026-07-10T11:00:00"))

    assert {call.kwargs["interval"] for call in client.get_historical_data.call_args_list[before:]} == {
        "FIVE_MINUTE", "FIFTEEN_MINUTE", "ONE_HOUR"
    }


def test_daily_cache_does_not_refresh_each_minute_during_session(tmp_path):
    now = [1000.0]
    service, client, _, _, gate = _service(tmp_path, now=now)
    service.fetch_timeframe_raw("NSE", "99926000", "1d", end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    service.fetch_timeframe_raw("NSE", "99926000", "1d", end_time=_at("2026-07-10T10:18:00"))

    assert client.get_historical_data.call_count - before == 0
    assert gate.calls == 1


def test_two_markets_evaluate_closed_coverage_from_independent_entries(tmp_path):
    now = [1000.0]
    service, client, _, _, _ = _service(tmp_path, now=now)
    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        service.fetch_all_with_capture(exchange, token, end_time=_at("2026-07-10T10:17:00"))
    before = client.get_historical_data.call_count

    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        service.fetch_all_with_capture(exchange, token, end_time=_at("2026-07-10T10:20:00"))

    calls = client.get_historical_data.call_args_list[before:]
    assert {(call.kwargs["exchange"], call.kwargs["symboltoken"], call.kwargs["interval"]) for call in calls} == {
        ("NSE", "99926000", "FIVE_MINUTE"),
        ("BSE", "99919000", "FIVE_MINUTE"),
    }


def test_closed_coverage_cache_precedes_cooldown_and_insufficient_coverage_does_not(tmp_path):
    now = [1000.0]
    service, client, cache, cooldown, gate = _service(tmp_path, now=now)
    covered_at = _at("2026-07-10T10:10:00")
    cache.set("NSE", "99926000", "5m", _response(covered_at))
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=20)

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=_at("2026-07-10T10:17:00"))
    assert client.get_historical_data.call_count == 0
    assert gate.calls == 0

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited") as raised:
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=_at("2026-07-10T10:20:00"))

    assert raised.value.failure["failure_type"] == "rate_limited"
    assert client.get_historical_data.call_count == 0
    assert gate.calls == 0
