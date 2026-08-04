from datetime import datetime, timedelta, timezone

import pytest

from services.analysis.india_vix_normalizer import normalize_india_vix_capture
from services.contracts.india_vix_regime_policy_v1 import classify_india_vix_regime
from services.paper_orchestration.india_vix_live_reader import IndiaVixLiveReader


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)


class Client:
    def __init__(self, row):
        self.row = row
        self.calls = 0

    def get_market_data(self, mode, exchange_tokens):
        self.calls += 1
        assert (mode, exchange_tokens) == ("FULL", {"NSE": ["99926017"]})
        return {"data": {"fetched": [self.row]}}


def master():
    return [{"token": "99926017", "symbol": "India VIX", "name": "INDIA VIX", "exch_seg": "NSE", "instrumenttype": "AMXIDX"}]


def row(**changes):
    value = {"ltp": 18.0, "close": 17.0, "tradingSymbol": "India VIX", "symbolToken": "99926017", "exchange": "NSE", "exchFeedTime": "03-Aug-2026 15:29:30"}
    value.update(changes)
    return value


def test_policy_is_exact_at_approved_boundaries_and_fails_closed():
    assert [classify_india_vix_regime(value) for value in (12.99, 13, 18, 20, 28)] == ["LOW", "NORMAL", "ELEVATED", "HIGH", "EXTREME"]
    assert [classify_india_vix_regime(value) for value in (None, 0, -1, float("nan"), float("inf"))] == ["UNAVAILABLE"] * 5


def test_reader_caches_master_and_quote_per_parent_cycle_then_normalizes_both_markets():
    master_calls = 0
    def fetch_master():
        nonlocal master_calls
        master_calls += 1
        return master()
    client = Client(row())
    clock_values = iter((NOW, NOW + timedelta(seconds=1)))
    reader = IndiaVixLiveReader(master_fetcher=fetch_master, market_client=client, clock=lambda: next(clock_values))
    capture = reader.capture("parent-1")
    assert reader.capture("parent-1") is capture
    assert (master_calls, client.calls, capture.source_status, capture.previous_close) == (1, 1, "READY", 17.0)
    nifty, sensex = normalize_india_vix_capture(capture)
    assert (nifty.underlying_symbol, nifty.exchange, nifty.normalized_volatility_regime) == ("NIFTY", "NSE", "ELEVATED")
    assert (sensex.underlying_symbol, sensex.exchange, sensex.normalized_volatility_regime) == ("SENSEX", "BSE", "ELEVATED")
    assert "99926017" in capture.to_json() and "secret" not in capture.to_json().lower()


@pytest.mark.parametrize("changes, blocker", [
    ({"symbolToken": "wrong"}, "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"),
    ({"exchFeedTime": "bad"}, "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN"),
    ({"exchFeedTime": "03-Aug-2026 15:00:00"}, "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH"),
])
def test_reader_fails_closed_without_fabricating_data(changes, blocker):
    client = Client(row(**changes))
    reader = IndiaVixLiveReader(master_fetcher=master, market_client=client, clock=lambda: NOW)
    capture = reader.capture("parent-1")
    assert blocker in capture.blockers
    snapshots = normalize_india_vix_capture(capture)
    if capture.provider_timestamp is None:
        assert snapshots == (None, None)
    else:
        assert all(snapshot.normalized_volatility_regime == "UNAVAILABLE" for snapshot in snapshots)


def test_reader_does_not_leak_provider_exception_text():
    class BrokenClient:
        def get_market_data(self, *_args):
            raise RuntimeError("password=never-print")
    capture = IndiaVixLiveReader(master_fetcher=master, market_client=BrokenClient(), clock=lambda: NOW).capture("parent-1")
    assert "password" not in capture.to_json().lower()
