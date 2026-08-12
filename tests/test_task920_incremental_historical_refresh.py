from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from services.broker.market_data_control import BrokerMarketDataRequestError
from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData


IST = ZoneInfo("Asia/Kolkata")
END = datetime(2026, 7, 10, 10, 20, tzinfo=IST)
INTERVALS = {"5m": 5, "15m": 15, "1h": 60, "1d": 1440}
LOOKBACK_DAYS = {"5m": 3, "15m": 10, "1h": 45, "1d": 365}
PROVIDER_INTERVALS = {
    "FIVE_MINUTE": "5m",
    "FIFTEEN_MINUTE": "15m",
    "ONE_HOUR": "1h",
    "ONE_DAY": "1d",
}


class Gate:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1
        return {"wait_seconds": 0.0}


def _row(timestamp, *, volume=10):
    return [timestamp.isoformat(), 100, 101, 99, 100, volume]


def _response(*rows):
    return {"status": True, "data": list(rows)}


def _deep_response(timeframe, latest, *, end=END):
    first = (end - timedelta(days=LOOKBACK_DAYS[timeframe], minutes=5)).replace(
        hour=9,
        minute=15,
        second=0,
        microsecond=0,
    )
    return _response(_row(first), _row(latest))


def _service(tmp_path, *, now, response):
    client = MagicMock()
    client.request_controller = SimpleNamespace(rate_limit_cooldown_seconds=20.0)
    client.get_historical_data.side_effect = response
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


def _tail_response(**kwargs):
    end = datetime.strptime(kwargs["todate"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    timeframe = PROVIDER_INTERVALS[kwargs["interval"]]
    interval = timedelta(minutes=INTERVALS[timeframe])
    required = {
        "5m": end.replace(second=0, microsecond=0) - interval,
        "15m": end.replace(minute=end.minute - (end.minute % 15), second=0, microsecond=0) - interval,
        "1h": end.replace(minute=0, second=0, microsecond=0) - interval,
        "1d": end.replace(hour=0, minute=0, second=0, microsecond=0),
    }[timeframe]
    start = datetime.strptime(kwargs["fromdate"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    return _response(_row(start, volume=111), _row(required, volume=222))


def _seed_deep_cache(cache, exchange, token, *, end=END):
    required = {
        "5m": datetime(2026, 7, 10, 10, 15, tzinfo=IST),
        "15m": datetime(2026, 7, 10, 10, 0, tzinfo=IST),
        "1h": datetime(2026, 7, 10, 9, 0, tzinfo=IST),
        "1d": datetime(2026, 7, 9, 0, 0, tzinfo=IST),
    }
    for timeframe, latest in required.items():
        cache.set(exchange, token, timeframe, _deep_response(timeframe, latest, end=end))


def test_incremental_tail_uses_one_interval_overlap_and_persists_merged_history(tmp_path):
    now = [1000.0]
    service, client, cache, _, _ = _service(tmp_path, now=now, response=_tail_response)
    cached_latest = datetime(2026, 7, 10, 10, 10, tzinfo=IST)
    cache.set("NSE", "99926000", "5m", _deep_response("5m", cached_latest))

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    client.get_historical_data.assert_called_once()
    call = client.get_historical_data.call_args.kwargs
    assert call["fromdate"] == "2026-07-10 10:05"
    assert call["todate"] == "2026-07-10 10:20"
    merged = cache.get_incremental_candidate("NSE", "99926000", "5m")["response"]["data"]
    assert [row[0] for row in merged] == sorted(row[0] for row in merged)
    assert len({row[0] for row in merged}) == len(merged)
    assert merged[0][0].startswith("2026-07-07T09:15:00")
    assert any(row[0] == "2026-07-10T10:15:00+05:30" for row in merged)


def test_tail_overlap_replaces_cached_row_by_exact_timestamp(tmp_path):
    now = [1000.0]
    cached_latest = datetime(2026, 7, 10, 10, 10, tzinfo=IST)

    def response(**kwargs):
        return _response(
            _row(cached_latest, volume=333),
            _row(datetime(2026, 7, 10, 10, 15, tzinfo=IST), volume=444),
        )

    service, client, cache, _, _ = _service(tmp_path, now=now, response=response)
    cache.set("NSE", "99926000", "5m", _deep_response("5m", cached_latest))
    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    merged = cache.get_incremental_candidate("NSE", "99926000", "5m")["response"]["data"]
    assert client.get_historical_data.call_count == 1
    assert [row for row in merged if row[0] == cached_latest.isoformat()][0][5] == 333


@pytest.mark.parametrize(
    "tail",
    (
        lambda: _response(_row(datetime(2026, 7, 10, 10, 10, tzinfo=IST))),
        lambda: _response(
            _row(datetime(2026, 7, 10, 10, 15, tzinfo=IST)),
            _row(datetime(2026, 7, 10, 10, 10, tzinfo=IST)),
        ),
        lambda: _response(["bad-timestamp", 100, 101, 99, 100, 10]),
    ),
)
def test_insufficient_or_malformed_tail_fails_closed_without_second_request(tmp_path, tail):
    now = [1000.0]
    service, client, cache, _, _ = _service(tmp_path, now=now, response=lambda **_: tail())
    cache.set("NSE", "99926000", "5m", _deep_response("5m", datetime(2026, 7, 10, 10, 10, tzinfo=IST)))

    with pytest.raises(ValueError):
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    assert client.get_historical_data.call_count == 1
    assert cache.get_incremental_candidate("NSE", "99926000", "5m")["response"]["data"][-1][0] == "2026-07-10T10:10:00+05:30"


def test_throttled_incremental_request_records_cooldown_without_full_retry(tmp_path):
    now = [1000.0]
    error = BrokerMarketDataRequestError("historical-data", 1, "rate_limited", "sanitized")
    service, client, cache, cooldown, _ = _service(tmp_path, now=now, response=error)
    cache.set("NSE", "99926000", "5m", _deep_response("5m", datetime(2026, 7, 10, 10, 10, tzinfo=IST)))

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    assert client.get_historical_data.call_count == 1
    assert cooldown.active()["reason"] == "HISTORICAL-DATA_RATE_LIMITED"


@pytest.mark.parametrize("cache_state", ("missing", "corrupt", "shallow"))
def test_cache_without_eligible_depth_uses_single_full_lookback_request(tmp_path, cache_state):
    now = [1000.0]
    service, client, cache, _, _ = _service(tmp_path, now=now, response=_tail_response)
    if cache_state == "corrupt":
        cache.file_path.write_text("not-json", encoding="utf-8")
    elif cache_state == "shallow":
        cache.set("NSE", "99926000", "5m", _response(_row(datetime(2026, 7, 10, 10, 10, tzinfo=IST))))

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    assert client.get_historical_data.call_count == 1
    assert client.get_historical_data.call_args.kwargs["fromdate"] == "2026-07-07 10:20"


def test_active_cooldown_with_insufficient_cached_tail_makes_no_request(tmp_path):
    now = [1000.0]
    service, client, cache, cooldown, gate = _service(tmp_path, now=now, response=_tail_response)
    cache.set("NSE", "99926000", "5m", _deep_response("5m", datetime(2026, 7, 10, 10, 10, tzinfo=IST)))
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=20)

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)

    assert client.get_historical_data.call_count == 0
    assert gate.calls == 0


def test_repeated_capture_before_next_boundary_is_zero_calls(tmp_path):
    now = [1000.0]
    service, client, cache, _, gate = _service(tmp_path, now=now, response=_tail_response)
    _seed_deep_cache(cache, "NSE", "99926000")

    service.fetch_all_with_capture("NSE", "99926000", end_time=END)

    assert client.get_historical_data.call_count == 0
    assert gate.calls == 0


def test_two_market_five_minute_boundary_uses_two_incremental_calls(tmp_path):
    now = [1000.0]
    service, client, cache, _, _ = _service(tmp_path, now=now, response=_tail_response)
    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        _seed_deep_cache(cache, exchange, token)
        cache.set(exchange, token, "5m", _deep_response("5m", datetime(2026, 7, 10, 10, 10, tzinfo=IST)))

    service.fetch_all_with_capture("NSE", "99926000", end_time=END)
    service.fetch_all_with_capture("BSE", "99919000", end_time=END)

    assert {(call.kwargs["exchange"], call.kwargs["interval"]) for call in client.get_historical_data.call_args_list} == {
        ("NSE", "FIVE_MINUTE"), ("BSE", "FIVE_MINUTE")
    }


def test_fifteen_minute_boundary_does_not_refresh_hour_or_daily(tmp_path):
    now = [1000.0]
    service, client, cache, _, _ = _service(tmp_path, now=now, response=_tail_response)
    _seed_deep_cache(cache, "NSE", "99926000")
    boundary = datetime(2026, 7, 10, 10, 30, tzinfo=IST)
    cache.set("NSE", "99926000", "5m", _deep_response("5m", datetime(2026, 7, 10, 10, 10, tzinfo=IST)))

    service.fetch_all_with_capture("NSE", "99926000", end_time=boundary)

    assert {call.kwargs["interval"] for call in client.get_historical_data.call_args_list} == {
        "FIVE_MINUTE", "FIFTEEN_MINUTE"
    }
