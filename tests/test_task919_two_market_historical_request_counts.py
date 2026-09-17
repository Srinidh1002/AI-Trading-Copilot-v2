from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.historical_data_cache import HistoricalDataCache
from services.historical_provider_cooldown import HistoricalProviderCooldown
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData


NOW = datetime(2026, 8, 10, 15, 30)
EXPECTED = {
    ("NSE", "99926000", "FIVE_MINUTE"),
    ("NSE", "99926000", "FIFTEEN_MINUTE"),
    ("NSE", "99926000", "ONE_HOUR"),
    ("NSE", "99926000", "ONE_DAY"),
    ("BSE", "99919000", "FIVE_MINUTE"),
    ("BSE", "99919000", "FIFTEEN_MINUTE"),
    ("BSE", "99919000", "ONE_HOUR"),
    ("BSE", "99919000", "ONE_DAY"),
}


class Gate:
    def __init__(self): self.calls = 0
    def acquire(self): self.calls += 1; return {"wait_seconds": 0.0}


def _response():
    return {"status": True, "data": [["2026-08-10T09:15:00+05:30", 100, 101, 99, 100, 10]]}


def test_two_market_capture_is_eight_cold_calls_and_zero_warm_calls(tmp_path):
    now = [1000.0]
    client = MagicMock()
    client.request_controller = SimpleNamespace(rate_limit_cooldown_seconds=20.0)
    client.get_historical_data.return_value = _response()
    cache = HistoricalDataCache(tmp_path / "history.json", time_function=lambda: now[0])
    gate = Gate()
    service = LiveMultiTimeframeData(
        client=client,
        cache=cache,
        provider_cooldown=HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: now[0]),
        historical_request_gate=gate,
    )

    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        service.fetch_all_with_capture(exchange, token, end_time=NOW)

    identities = {
        (call.kwargs["exchange"], call.kwargs["symboltoken"], call.kwargs["interval"])
        for call in client.get_historical_data.call_args_list
    }
    assert client.get_historical_data.call_count == 8
    assert identities == EXPECTED
    assert len(client.get_historical_data.call_args_list) == len(identities)
    assert gate.calls == 8
    assert HistoricalProviderCooldown(tmp_path / "cooldown.json", time_function=lambda: now[0]).active() is None

    before = client.get_historical_data.call_count
    for exchange, token in (("NSE", "99926000"), ("BSE", "99919000")):
        service.fetch_all_with_capture(exchange, token, end_time=NOW)
    assert client.get_historical_data.call_count - before == 0
    assert gate.calls == 8
