import json
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


class Gate:
    def __init__(self): self.calls = 0
    def acquire(self): self.calls += 1; return {"wait_seconds": 0.0}


def _row(timestamp): return [timestamp.isoformat(), 100, 101, 99, 100, 10]
def _response(*rows): return {"status": True, "data": list(rows)}


def _deep_response(latest):
    return _response(_row(datetime(2026, 7, 7, 9, 15, tzinfo=IST)), _row(latest))


def _service(tmp_path, provider):
    now = [1000.0]
    client = MagicMock()
    client.request_controller = SimpleNamespace(rate_limit_cooldown_seconds=20.0)
    client.get_historical_data.side_effect = provider
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: now[0])
    cooldown = HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: now[0])
    gate = Gate()
    return LiveMultiTimeframeData(client=client, cache=cache, provider_cooldown=cooldown, historical_request_gate=gate), client, cache, cooldown, gate


def _tail(**kwargs):
    start = datetime.strptime(kwargs["fromdate"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    return _response(_row(start), _row(datetime(2026, 7, 10, 10, 15, tzinfo=IST)))


def test_cache_hit_diagnostic_is_none_mode_without_gate_or_provider(tmp_path):
    service, client, cache, _, gate = _service(tmp_path, _tail)
    cache.set("NSE", "99926000", "5m", _deep_response(datetime(2026, 7, 10, 10, 15, tzinfo=IST)))

    capture = service.fetch_all_with_capture("NSE", "99926000", end_time=END)
    value = capture["request_diagnostics"]["5m"]

    assert value["refresh_mode"] == "NONE"
    assert value["provider_attempted"] is False and value["gate_acquired"] is False
    assert client.get_historical_data.call_count == 3 and gate.calls == 3


def test_incremental_diagnostic_exposes_overlap_and_successful_merge(tmp_path):
    service, client, cache, _, gate = _service(tmp_path, _tail)
    cache.set("NSE", "99926000", "5m", _deep_response(datetime(2026, 7, 10, 10, 10, tzinfo=IST)))

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)
    value = service._request_diagnostics[("NSE", "99926000", "5m")]

    assert (value["refresh_mode"], value["request_from"], value["request_to"]) == ("INCREMENTAL", "2026-07-10 10:05", "2026-07-10 10:20")
    assert value["provider_result"] == value["merge_result"] == value["cache_write_result"] == "SUCCESS"
    assert client.get_historical_data.call_count == gate.calls == 1


def test_full_diagnostic_exposes_full_range_and_no_merge(tmp_path):
    service, client, _, _, _ = _service(tmp_path, _tail)

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)
    value = service._request_diagnostics[("NSE", "99926000", "5m")]

    assert (value["refresh_mode"], value["request_from"], value["request_to"]) == ("FULL", "2026-07-07 10:20", "2026-07-10 10:20")
    assert value["provider_result"] == value["cache_write_result"] == "SUCCESS"
    assert value["merge_result"] == "NOT_REQUIRED" and client.get_historical_data.call_count == 1


def test_cooldown_diagnostic_has_no_provider_or_gate(tmp_path):
    service, client, _, cooldown, gate = _service(tmp_path, _tail)
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=20)

    with pytest.raises(BrokerMarketDataRequestError): service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)
    value = service._request_diagnostics[("NSE", "99926000", "5m")]

    assert (value["provider_result"], value["failure_reason"], value["provider_attempted"], value["gate_acquired"]) == ("NOT_ATTEMPTED", "HISTORICAL-DATA_RATE_LIMITED", False, False)
    assert client.get_historical_data.call_count == gate.calls == 0


@pytest.mark.parametrize(
    ("error", "result"),
    (
        (BrokerMarketDataRequestError("historical-data", 1, "rate_limited", "sanitized"), "RATE_LIMITED"),
        (RuntimeError("sanitized provider failure"), "FAILED"),
    ),
)
def test_provider_error_diagnostic_preserves_exception_and_result(tmp_path, error, result):
    service, client, _, _, gate = _service(tmp_path, error)

    with pytest.raises(type(error)): service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=END)
    value = service._request_diagnostics[("NSE", "99926000", "5m")]

    assert value["provider_attempted"] is True and value["gate_acquired"] is True
    assert value["provider_result"] == result and client.get_historical_data.call_count == gate.calls == 1


def test_diagnostics_are_payload_and_secret_free_and_markets_are_independent(tmp_path):
    service, _, cache, _, _ = _service(tmp_path, _tail)
    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        cache.set(exchange, token, "5m", _deep_response(datetime(2026, 7, 10, 10, 15, tzinfo=IST)))
        service.fetch_all_with_capture(exchange, token, end_time=END)

    nifty = service._request_diagnostics[("NSE", "99926000", "5m")]
    sensex = service._request_diagnostics[("BSE", "99919000", "5m")]
    serialized = json.dumps({"nifty": nifty, "sensex": sensex}, sort_keys=True).lower()

    assert (nifty["exchange"], sensex["exchange"]) == ("NSE", "BSE")
    assert not any(secret in serialized for secret in ("api_key", "pin", "totp", "cookie", "header", "payload", "auth_token"))
