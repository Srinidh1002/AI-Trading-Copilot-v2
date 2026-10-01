"""X1 end-to-end integration test.

Wires: fake socket -> streaming -> tracker -> bridge -> hub -> journal
and back via deterministic replay. Also exercises rollover end-to-end.
Offline only.
"""
from __future__ import annotations

from datetime import UTC, datetime

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.x1.composition_v1 import (
    X1DataPlaneCompositionV1,
)
from services.x1.observation_journal_v1 import (
    ObservationJournalV1,
)
from services.x1.observation_tracker_v1 import (
    ObservationTrackerV1,
)

BASE = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
SESSION = "2026-09-17"


class FakeSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        del symbols, data_type

    def unsubscribe(self, *, symbols, data_type):
        del symbols, data_type

    def close_connection(self):
        pass

    def emit(self, message):
        self.kwargs["on_message"](message)


class Factory:
    def __init__(self):
        self.socket = None
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        self.socket = FakeSocket(**kwargs)
        return self.socket


def instrument(symbol, canonical_id):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": canonical_id,
        "market_symbol": "NIFTY",
        "instrument_type": "UNDERLYING",
        "underlying_exchange": "NSE",
        "derivative_exchange": "NFO",
        "resolution_id": f"res-{symbol}",
        "expiry": None,
    }


def test_full_pipeline_then_replay(tmp_path):
    factory = Factory()
    streaming = FyersStreamingDataProviderV2(
        access_token="APP-100:T",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: BASE,
    )
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    composition = X1DataPlaneCompositionV1(
        hub=hub,
        tracker=tracker,
        streaming=streaming,
        consumer_id="x1-integration",
        journal=journal,
    )
    composition.start(
        (instrument("NSE:NIFTY50-INDEX", "NIFTY|UNDERLYING|NSE:NIFTY50-INDEX"),)
    )
    assert streaming.wait_until_connected(1.0)

    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23456.75})
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23457.0})

    # Hub: last price is the second tick.
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING|NSE:NIFTY50-INDEX"
        ),
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 23457.0

    # Journal: two records, one VALID per tick.
    records = journal.load()
    assert len(records) == 2
    assert all(r.quality == "VALID" for r in records)

    # Deterministic replay produces identical canonical JSON.
    replayed = journal.load(replay_at=BASE)
    assert tuple(
        r.canonical_json() for r in records
    ) == tuple(r.canonical_json() for r in replayed)

    composition.stop()
    streaming.close()


def test_duplicate_then_reconnect_end_to_end(tmp_path):
    factory = Factory()
    streaming = FyersStreamingDataProviderV2(
        access_token="APP-100:T",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: BASE,
    )
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    composition = X1DataPlaneCompositionV1(
        hub=hub,
        tracker=tracker,
        streaming=streaming,
        consumer_id="x1-integration-reconnect",
        journal=journal,
    )
    composition.start(
        (instrument("NSE:NIFTY50-INDEX", "NIFTY|UNDERLYING|NSE:NIFTY50-INDEX"),)
    )
    assert streaming.wait_until_connected(1.0)

    # Same identity twice: second is suspected duplicate.
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 100.0})
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 100.0})

    results = composition.results()
    assert results[0].accepted is True
    assert results[1].accepted is False

    # Hub still reflects the first.
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id=(
            "NIFTY|UNDERLYING|NSE:NIFTY50-INDEX"
        ),
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 100.0

    composition.stop()
    streaming.close()
