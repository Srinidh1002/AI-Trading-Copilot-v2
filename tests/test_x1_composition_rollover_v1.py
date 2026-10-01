from __future__ import annotations

from datetime import UTC, datetime

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.contracts.market_data_v2 import (
    MarketDataProvenanceV2,
    MarketQuoteV2,
)
from services.x1.composition_v1 import (
    X1DataPlaneCompositionV1,
)
from services.x1.observation_tracker_v1 import (
    ObservationTrackerV1,
)

BASE = datetime(2026, 9, 30, 16, 0, tzinfo=UTC)


class ControllableSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connect_calls = 0
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.fail_subscribe_symbols = set()
        self.fail_unsubscribe_symbols = set()

    def connect(self):
        self.connect_calls += 1
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        symbols_t = tuple(symbols)
        self.subscribe_calls.append((symbols_t, data_type))
        if symbols_t in self.fail_subscribe_symbols:
            raise RuntimeError("subscribe rejected")

    def unsubscribe(self, *, symbols, data_type):
        symbols_t = tuple(symbols)
        self.unsubscribe_calls.append((symbols_t, data_type))
        if symbols_t in self.fail_unsubscribe_symbols:
            raise RuntimeError("unsubscribe rejected")

    def close_connection(self):
        pass

    def emit(self, message):
        self.kwargs["on_message"](message)


class CapturingFactory:
    def __init__(self):
        self.socket = None
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        self.socket = ControllableSocket(**kwargs)
        return self.socket


def instrument(
    symbol,
    *,
    market="NIFTY",
    instrument_type="FUTURE",
    resolution_id=None,
    canonical_id=None,
    expiry=None,
    underlying_exchange="NSE",
    derivative_exchange="NFO",
):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": (
            canonical_id or f"{market}|{instrument_type}|{symbol}"
        ),
        "market_symbol": market,
        "instrument_type": instrument_type,
        "underlying_exchange": underlying_exchange,
        "derivative_exchange": derivative_exchange,
        "resolution_id": resolution_id or f"res-{symbol}",
        "expiry": expiry,
    }


def build(*, now=BASE):
    factory = CapturingFactory()
    streaming = FyersStreamingDataProviderV2(
        access_token="APP-100:T",
        client_id="APP-100",
        log_path="TEMP_LOG",
        socket_factory=factory,
        reconnect=True,
        now=lambda: now,
    )
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: now)
    composition = X1DataPlaneCompositionV1(
        hub=hub,
        tracker=tracker,
        streaming=streaming,
        consumer_id="x1-rollover-test",
    )
    return factory, streaming, hub, composition


class FakeResolver:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def resolve(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("resolver exhausted")
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def publish_old_quote(hub, previous):
    hub.publish_quote(
        MarketQuoteV2(
            quote_id="q-old",
            market_symbol=previous["market_symbol"],
            exchange=previous["derivative_exchange"],
            instrument_type=previous["instrument_type"],
            canonical_instrument_id=(
                previous["canonical_instrument_id"]
            ),
            last_price=100.0,
            bid_price=None,
            ask_price=None,
            volume=None,
            open_interest=None,
            provenance=MarketDataProvenanceV2(
                provider="FYERS",
                provider_symbol=previous["provider_symbol"],
                provider_exchange=previous["derivative_exchange"],
                source_type="LIVE",
                observed_at=BASE,
                received_at=BASE,
            ),
        )
    )


def test_rollover_before_start_returns_not_started():
    factory, streaming, hub, composition = build()
    outcome = composition.rollover(
        previous_instrument=instrument("NSE:NIFTY26SEPFUT"),
        resolver=FakeResolver([]),
        as_of=BASE,
    )
    assert outcome.status == "NOT_STARTED"
    assert outcome.error_code == "composition_not_started"
    streaming.close()


def test_rollover_not_expired_preserves_state():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([prev]),
        as_of=BASE,
    )
    assert outcome.status == "NOT_EXPIRED"
    assert composition.subscription_id is not None
    assert composition.current_instrument is not None
    assert (
        composition.current_instrument["resolution_id"]
        == prev["resolution_id"]
    )
    streaming.close()


def test_rollover_replaced_swaps_subscriptions_and_invalidates():
    factory, streaming, hub, composition = build()
    prev = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-old",
        canonical_id="NIFTY|FUTURE|old",
    )
    new = instrument(
        "NSE:NIFTY26OCTFUT",
        resolution_id="res-new",
        canonical_id="NIFTY|FUTURE|new",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    publish_old_quote(hub, prev)
    assert hub.snapshot_counts()["quotes"] == 1

    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    assert outcome.status == "REPLACED"
    assert outcome.new_resolution_id == "res-new"
    assert outcome.hub_invalidation_counts["quotes"] == 1
    assert hub.snapshot_counts()["quotes"] == 0
    assert (
        composition.current_instrument["resolution_id"] == "res-new"
    )
    # New instrument is physically subscribed.
    assert (
        ("NSE:NIFTY26OCTFUT",), "SymbolUpdate"
    ) in factory.socket.subscribe_calls
    streaming.close()


def test_rollover_subscribe_failure_leaves_old_intact():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    new = instrument(
        "NSE:NIFTY26OCTFUT", resolution_id="res-new"
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    factory.socket.fail_subscribe_symbols = {
        ("NSE:NIFTY26OCTFUT",)
    }
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    assert outcome.status == "UNAVAILABLE"
    assert "subscribe_new" in (outcome.error_code or "")
    assert composition.subscription_id is not None
    assert (
        composition.current_instrument["resolution_id"]
        == prev["resolution_id"]
    )
    streaming.close()


def test_rollover_unsubscribe_failure_triggers_rollback():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    new = instrument(
        "NSE:NIFTY26OCTFUT", resolution_id="res-new"
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    factory.socket.fail_unsubscribe_symbols = {
        ("NSE:NIFTY26SEPFUT",)
    }
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    assert outcome.status == "ROLLBACK"
    assert "unsubscribe_old" in (outcome.error_code or "")
    # New subscription must have been rolled back.
    assert (
        (("NSE:NIFTY26OCTFUT",), "SymbolUpdate")
        in factory.socket.unsubscribe_calls
    )
    streaming.close()


def test_rollover_unavailable_no_state_change():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver(
            [RuntimeError("expired"), RuntimeError("no replacement")]
        ),
        as_of=BASE,
    )
    assert outcome.status == "UNAVAILABLE"
    assert composition.subscription_id is not None
    streaming.close()


def test_rollover_ambiguous_no_state_change():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    same = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id=prev["resolution_id"],
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), same]),
        as_of=BASE,
    )
    assert outcome.status == "AMBIGUOUS"
    streaming.close()


def test_rollover_underlying_is_noop():
    factory, streaming, hub, composition = build()
    prev = instrument(
        "NSE:NIFTY50-INDEX",
        instrument_type="UNDERLYING",
        underlying_exchange="NSE",
        derivative_exchange="NFO",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    resolver = FakeResolver([])
    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=resolver,
        as_of=BASE,
    )
    assert outcome.status == "NOT_EXPIRED"
    assert resolver.calls == []
    streaming.close()


def test_rollover_history_is_recorded():
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    new = instrument(
        "NSE:NIFTY26OCTFUT", resolution_id="res-new"
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    history = composition.rollover_history()
    assert len(history) == 1
    assert history[0].status == "REPLACED"
    streaming.close()


def test_rollover_does_not_mix_generations_across_new_instrument():
    # After rollover the composition's subscription_id is the new one,
    # so a subsequent generation bump from the same socket does not
    # create cross-instrument confusion: the old instrument is gone
    # from the physical subscription set.
    factory, streaming, hub, composition = build()
    prev = instrument("NSE:NIFTY26SEPFUT")
    new = instrument(
        "NSE:NIFTY26OCTFUT", resolution_id="res-new"
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    composition.rollover(
        previous_instrument=prev,
        resolver=FakeResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    # The old symbol has been removed from the streaming adapter's
    # desired set.
    snapshot = streaming.snapshot()
    assert snapshot["desired_symbol_count"] == 1
    streaming.close()
