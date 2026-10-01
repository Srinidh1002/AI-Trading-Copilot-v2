from __future__ import annotations

from datetime import UTC, datetime

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.x1.composition_v1 import (
    X1CompositionError,
    X1DataPlaneCompositionV1,
)
from services.x1.observation_tracker_v1 import (
    ObservationTrackerV1,
)

BASE = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)


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

    def reconnect(self):
        self.kwargs["on_close"]("SDK_RECONNECT")
        self.kwargs["on_connect"]()


class CapturingFactory:
    def __init__(self):
        self.socket = None
        self.kwargs = None
        self.call_count = 0

    def __call__(self, **kwargs):
        self.call_count += 1
        self.kwargs = kwargs
        self.socket = FakeSocket(**kwargs)
        return self.socket


def instrument(symbol, *, market="NIFTY", instrument_type="UNDERLYING"):
    return {
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": f"{market}|{instrument_type}|{symbol}",
        "market_symbol": market,
        "instrument_type": instrument_type,
    }


def build_composition(*, now=BASE):
    factory = CapturingFactory()
    streaming = FyersStreamingDataProviderV2(
        access_token="APP-100:RAW_TOKEN",
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
        consumer_id="x1-phase-3-test",
    )
    return factory, streaming, hub, composition


def test_composition_publishes_valid_tick():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 23456.75})
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 23456.75
    assert len(composition.results()) == 1
    assert composition.results()[0].accepted is True
    composition.stop()
    streaming.close()


def test_duplicate_tick_does_not_overwrite_hub():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 1.0})
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 1.0})
    results = composition.results()
    assert len(results) == 2
    assert results[0].accepted is True
    assert results[1].accepted is False
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 1.0
    composition.stop()
    streaming.close()


def test_invalid_price_is_not_published():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    factory.socket.emit({"symbol": "NSE:NIFTY50-INDEX", "ltp": 0})
    results = composition.results()
    # The streaming adapter filters ltp<=0 before it ever reaches a
    # consumer, so the bridge never sees it. No result is recorded and
    # nothing is in the hub.
    assert results == ()
    import pytest

    from services.broker.shared_market_data_hub_v2 import (
        MarketDataUnavailableError,
    )

    with pytest.raises(MarketDataUnavailableError):
        hub.get_quote(
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
    composition.stop()
    streaming.close()


def test_start_is_idempotent_fail_closed():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    import pytest

    with pytest.raises(X1CompositionError):
        composition.start((instrument("NSE:NIFTY50-INDEX"),))
    composition.stop()
    streaming.close()


def test_stop_is_idempotent():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    composition.stop()
    composition.stop()  # must not raise
    streaming.close()


def test_composition_constructor_rejects_bad_inputs():
    import pytest

    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)

    with pytest.raises(X1CompositionError):
        X1DataPlaneCompositionV1(
            hub=hub,
            tracker=tracker,
            streaming=None,  # type: ignore[arg-type]
            consumer_id="x",
        )
    with pytest.raises(X1CompositionError):
        X1DataPlaneCompositionV1(
            hub=hub,
            tracker=tracker,
            streaming=FyersStreamingDataProviderV2(
                access_token="APP-100:T",
                client_id="APP-100",
                log_path="TEMP_LOG",
                socket_factory=CapturingFactory(),
                now=lambda: BASE,
            ),
            consumer_id="",
        )


def test_composition_never_publishes_when_generation_is_stale():
    factory, streaming, hub, composition = build_composition()
    composition.start((instrument("NSE:NIFTY50-INDEX"),))
    assert streaming.wait_until_connected(1.0)
    # Emit a tick, then simulate a reconnect so the generation advances
    # to 2. A late record carrying generation 1 must not be accepted.
    stale_record = {
        "provider": "FYERS",
        "provider_symbol": "NSE:NIFTY50-INDEX",
        "ltp": 100.0,
        "ts": BASE,
        "received_at": BASE,
        "timestamp_source": "PROVIDER",
        "canonical_instrument_id": "NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
        "market_symbol": "NIFTY",
        "instrument_type": "UNDERLYING",
        "connection_generation": 1,
    }
    factory.socket.reconnect()
    composition._on_tick(stale_record)  # type: ignore[attr-defined]
    results = composition.results()
    assert len(results) == 1
    assert results[0].accepted is False
    from services.x1.observation_tracker_v1 import (
        ObservationQualityV1,
    )
    assert (
        results[0].quality is ObservationQualityV1.STALE_GENERATION
    )
    composition.stop()
    streaming.close()
