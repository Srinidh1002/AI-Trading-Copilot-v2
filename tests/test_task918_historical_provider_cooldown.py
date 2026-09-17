from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.broker.market_data_control import BrokerMarketDataRequestError
from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData


NOW = datetime(2026, 8, 10, 15, 30)


def _response():
    return {"status": True, "data": [["2026-08-10T09:15:00+05:30", 100, 101, 99, 100, 10]]}


def _service(tmp_path, *, now, client, cache=None, cooldown=None):
    cache = cache or HistoricalDataCache(file_path=tmp_path / "history.json", time_function=lambda: now[0])
    cooldown = cooldown or HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: now[0])
    return LiveMultiTimeframeData(client=client, cache=cache, provider_cooldown=cooldown), cache, cooldown


def _client():
    client = MagicMock()
    client.request_controller = SimpleNamespace(rate_limit_cooldown_seconds=20.0)
    client.get_historical_data.return_value = _response()
    return client


def test_durable_cache_hit_avoids_provider_request(tmp_path):
    now = [1000.0]
    client = _client()
    service, cache, _ = _service(tmp_path, now=now, client=client)
    cache.set("NSE", "99926000", "5m", _response(), requested_until=NOW.isoformat())

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)

    client.get_historical_data.assert_not_called()


def test_insufficient_or_stale_cache_requests_provider_when_not_throttled(tmp_path):
    now = [1000.0]
    client = _client()
    service, cache, _ = _service(tmp_path, now=now, client=client)
    cache.set("NSE", "99926000", "5m", _response(), requested_until=datetime(2026, 8, 10, 10, 0).isoformat())

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    assert client.get_historical_data.call_count == 1

    now[0] += 241.0
    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    assert client.get_historical_data.call_count == 2


def test_first_rate_limit_persists_cooldown_and_repeated_request_does_not_hit_provider(tmp_path):
    now = [1000.0]
    client = _client()
    client.get_historical_data.side_effect = BrokerMarketDataRequestError("historical-data", 1, "rate_limited", "sanitized")
    service, _, cooldown = _service(tmp_path, now=now, client=client)

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    assert cooldown.active()["reason"] == "HISTORICAL-DATA_RATE_LIMITED"

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    assert client.get_historical_data.call_count == 1


def test_cooldown_survives_restart_expires_deterministically_and_allows_retry(tmp_path):
    now = [1000.0]
    client = _client()
    first, _, cooldown = _service(tmp_path, now=now, client=client)
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=20)
    restarted, _, _ = _service(tmp_path, now=now, client=client)

    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        restarted.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    client.get_historical_data.assert_not_called()

    now[0] += 20.0
    restarted.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    client.get_historical_data.assert_called_once()


def test_cache_is_still_usable_during_historical_cooldown_and_markets_are_isolated(tmp_path):
    now = [1000.0]
    client = _client()
    service, cache, cooldown = _service(tmp_path, now=now, client=client)
    cache.set("NSE", "99926000", "5m", _response(), requested_until=NOW.isoformat())
    cooldown.record_rate_limit(reason="HISTORICAL-DATA_RATE_LIMITED", cooldown_seconds=20)

    service.fetch_timeframe_raw("NSE", "99926000", "5m", end_time=NOW)
    client.get_historical_data.assert_not_called()
    with pytest.raises(BrokerMarketDataRequestError, match="rate_limited"):
        service.fetch_timeframe_raw("BSE", "99919000", "5m", end_time=NOW)


def test_one_capture_requests_each_timeframe_once_and_rate_limit_evidence_is_sanitized(tmp_path, monkeypatch):
    now = [1000.0]
    client = _client()
    client.get_historical_data.side_effect = BrokerMarketDataRequestError("historical-data", 1, "rate_limited", "sanitized")
    service, _, _ = _service(tmp_path, now=now, client=client)
    monkeypatch.setattr("services.market.live_multi_timeframe_data.TIMEFRAME_CONFIG", {"5m": {"interval": "FIVE_MINUTE", "lookback_days": 3}, "15m": {"interval": "FIFTEEN_MINUTE", "lookback_days": 10}})

    capture = service.fetch_all_with_capture("NSE", "99926000", end_time=NOW)

    assert client.get_historical_data.call_count == 1
    assert capture["cache_metadata"]["5m"]["failure_reason"] == "HISTORICAL-DATA_RATE_LIMITED"
    assert capture["cache_metadata"]["15m"]["failure_reason"] == "HISTORICAL-DATA_RATE_LIMITED"
