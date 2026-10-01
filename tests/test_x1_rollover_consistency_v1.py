from __future__ import annotations

from datetime import UTC, datetime

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    MarketDataUnavailableError,
    SharedMarketDataHubV2,
)
from services.contracts.market_data_v2 import (
    MarketDataProvenanceV2,
    MarketQuoteV2,
)
from services.x1.composition_v1 import (
    STATUS_MULTI_INSTRUMENT,
    STATUS_REPLACED,
    STATUS_REPLACED_DEGRADED,
    X1DataPlaneCompositionV1,
)
from services.x1.observation_journal_v1 import (
    ObservationJournalV1,
)
from services.x1.observation_tracker_v1 import (
    ObservationTrackerV1,
)

BASE = datetime(2026, 9, 30, 16, 0, tzinfo=UTC)
SESSION = "2026-09-30"


class FakeSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connect_calls = 0
        self.subscribe_calls = []
        self.unsubscribe_calls = []

    def connect(self):
        self.connect_calls += 1
        self.kwargs["on_connect"]()

    def subscribe(self, *, symbols, data_type):
        self.subscribe_calls.append((tuple(symbols), data_type))

    def unsubscribe(self, *, symbols, data_type):
        self.unsubscribe_calls.append((tuple(symbols), data_type))

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


class ScriptedResolver:
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


def instrument(symbol, *, resolution_id, canonical_id):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": canonical_id,
        "market_symbol": "NIFTY",
        "instrument_type": "FUTURE",
        "underlying_exchange": "NSE",
        "derivative_exchange": "NFO",
        "resolution_id": resolution_id,
        "expiry": "2026-09-30",
    }


def underlying(symbol, *, resolution_id, canonical_id):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "provider_token": None,
        "canonical_instrument_id": canonical_id,
        "market_symbol": "NIFTY",
        "instrument_type": "UNDERLYING",
        "underlying_exchange": "NSE",
        "derivative_exchange": "NFO",
        "resolution_id": resolution_id,
        "expiry": None,
    }


def build(*, journal=None, require_journal=False, **kwargs):
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
    composition = X1DataPlaneCompositionV1(
        hub=hub,
        tracker=tracker,
        streaming=streaming,
        consumer_id="x1-rc-test",
        journal=journal,
        require_journal=require_journal,
        **kwargs,
    )
    return factory, streaming, hub, composition


def publish_quote(hub, inst, price=100.0):
    hub.publish_quote(
        MarketQuoteV2(
            quote_id="q-old",
            market_symbol=inst["market_symbol"],
            exchange=inst["derivative_exchange"],
            instrument_type=inst["instrument_type"],
            canonical_instrument_id=inst["canonical_instrument_id"],
            last_price=price,
            bid_price=None,
            ask_price=None,
            volume=None,
            open_interest=None,
            provenance=MarketDataProvenanceV2(
                provider="FYERS",
                provider_symbol=inst["provider_symbol"],
                provider_exchange=inst["derivative_exchange"],
                source_type="LIVE",
                observed_at=BASE,
                received_at=BASE,
            ),
        )
    )


def test_invalidation_failure_yields_replaced_degraded():
    factory, streaming, hub, composition = build()
    prev = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-old",
        canonical_id="NIFTY:FUTURE:2026-09-30",
    )
    new = instrument(
        "NSE:NIFTY26OCTFUT",
        resolution_id="res-new",
        canonical_id="NIFTY:FUTURE:2026-10-28",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    publish_quote(hub, prev, price=100.0)

    original = hub.invalidate_instrument

    def failing(**_kwargs):
        raise RuntimeError("forced invalidation failure")

    hub.invalidate_instrument = failing  # type: ignore[method-assign]
    try:
        outcome = composition.rollover(
            previous_instrument=prev,
            resolver=ScriptedResolver(
                [RuntimeError("expired"), new]
            ),
            as_of=BASE,
        )
        assert outcome.status == STATUS_REPLACED_DEGRADED
        assert outcome.pending_invalidation is True
        assert outcome.error_code is not None
        assert outcome.error_code.startswith("invalidate:")
        assert composition.pending_invalidation_ids() == (
            "NIFTY:FUTURE:2026-09-30",
        )
        # Old instrument's cached data is still in the hub.
        assert hub.snapshot_counts()["quotes"] == 1
    finally:
        hub.invalidate_instrument = original  # type: ignore[method-assign]
    streaming.close()


def test_pending_invalidation_retried_on_next_tick():
    factory, streaming, hub, composition = build()
    prev = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-old",
        canonical_id="NIFTY:FUTURE:2026-09-30",
    )
    new = instrument(
        "NSE:NIFTY26OCTFUT",
        resolution_id="res-new",
        canonical_id="NIFTY:FUTURE:2026-10-28",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)
    publish_quote(hub, prev, price=100.0)

    original = hub.invalidate_instrument
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first fails")
        return original(**kwargs)

    hub.invalidate_instrument = flaky  # type: ignore[method-assign]
    try:
        outcome = composition.rollover(
            previous_instrument=prev,
            resolver=ScriptedResolver(
                [RuntimeError("expired"), new]
            ),
            as_of=BASE,
        )
        assert outcome.status == STATUS_REPLACED_DEGRADED
        assert composition.pending_invalidation_ids() == (
            "NIFTY:FUTURE:2026-09-30",
        )

        factory.socket.emit(
            {"symbol": "NSE:NIFTY26OCTFUT", "ltp": 200.0}
        )

        assert composition.pending_invalidation_ids() == ()

        # Old instrument's cached quote must be gone. The new tick
        # publishes its own quote under the new canonical id.
        old_available = True
        try:
            hub.get_quote(
                provider="FYERS",
                market_symbol="NIFTY",
                exchange="NFO",
                instrument_type="FUTURE",
                canonical_instrument_id="NIFTY:FUTURE:2026-09-30",
                max_age_seconds=3600,
                now=BASE,
            )
        except MarketDataUnavailableError:
            old_available = False
        assert old_available is False

        new_quote = hub.get_quote(
            provider="FYERS",
            market_symbol="NIFTY",
            exchange="NFO",
            instrument_type="FUTURE",
            canonical_instrument_id="NIFTY:FUTURE:2026-10-28",
            max_age_seconds=3600,
            now=BASE,
        )
        assert new_quote.last_price == 200.0
    finally:
        hub.invalidate_instrument = original  # type: ignore[method-assign]
    streaming.close()


def test_late_old_instrument_callback_is_refused():
    factory, streaming, hub, composition = build()
    prev = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-old",
        canonical_id="NIFTY:FUTURE:2026-09-30",
    )
    new = instrument(
        "NSE:NIFTY26OCTFUT",
        resolution_id="res-new",
        canonical_id="NIFTY:FUTURE:2026-10-28",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)

    outcome = composition.rollover(
        previous_instrument=prev,
        resolver=ScriptedResolver([RuntimeError("expired"), new]),
        as_of=BASE,
    )
    assert outcome.status == STATUS_REPLACED

    results_before = len(composition.results())
    composition._on_tick({  # type: ignore[attr-defined]
        "provider": "FYERS",
        "provider_symbol": "NSE:NIFTY26SEPFUT",
        "ltp": 999.0,
        "ts": BASE,
        "received_at": BASE,
        "timestamp_source": "PROVIDER",
        "canonical_instrument_id": "NIFTY:FUTURE:2026-09-30",
        "market_symbol": "NIFTY",
        "instrument_type": "FUTURE",
        "connection_generation": 1,
    })
    assert len(composition.results()) == results_before
    assert composition.retired_canonical_ids() == frozenset(
        {"NIFTY:FUTURE:2026-09-30"}
    )
    streaming.close()


def test_multi_instrument_composition_refuses_rollover():
    factory, streaming, hub, composition = build()
    a = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-a",
        canonical_id="NIFTY:FUTURE:2026-09-30",
    )
    b = instrument(
        "NSE:BANKNIFTY26SEPFUT",
        resolution_id="res-b",
        canonical_id="BANKNIFTY:FUTURE:2026-09-30",
    )
    composition.start((a, b))
    assert streaming.wait_until_connected(1.0)

    outcome = composition.rollover(
        previous_instrument=a,
        resolver=ScriptedResolver([a]),
        as_of=BASE,
    )
    assert outcome.status == STATUS_MULTI_INSTRUMENT
    assert outcome.error_code == (
        "multi_instrument_rollover_unsupported"
    )
    assert composition.pending_invalidation_ids() == ()
    streaming.close()


def test_pending_queue_full_refuses_new_rollover():
    factory, streaming, hub, composition = build(
        max_pending_invalidations=1
    )
    prev = instrument(
        "NSE:NIFTY26SEPFUT",
        resolution_id="res-old",
        canonical_id="NIFTY:FUTURE:2026-09-30",
    )
    new = instrument(
        "NSE:NIFTY26OCTFUT",
        resolution_id="res-new",
        canonical_id="NIFTY:FUTURE:2026-10-28",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)

    original = hub.invalidate_instrument

    def failing(**_kwargs):
        raise RuntimeError("forced")

    hub.invalidate_instrument = failing  # type: ignore[method-assign]
    try:
        first = composition.rollover(
            previous_instrument=prev,
            resolver=ScriptedResolver(
                [RuntimeError("expired"), new]
            ),
            as_of=BASE,
        )
        assert first.status == STATUS_REPLACED_DEGRADED
        assert len(composition.pending_invalidation_ids()) == 1

        # A second rollover from the new instrument would try to add
        # another pending entry. The queue is at capacity.
        next_contract = instrument(
            "NSE:NIFTY26NOVFUT",
            resolution_id="res-nov",
            canonical_id="NIFTY:FUTURE:2026-11-25",
        )
        second = composition.rollover(
            previous_instrument=new,
            resolver=ScriptedResolver(
                [RuntimeError("expired"), next_contract]
            ),
            as_of=BASE,
        )
        assert second.status == "PENDING_QUEUE_FULL"
        assert second.error_code == (
            "pending_invalidation_queue_full"
        )
    finally:
        hub.invalidate_instrument = original  # type: ignore[method-assign]
    streaming.close()


def test_journal_append_failure_marks_health_unhealthy(tmp_path):
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    factory, streaming, hub, composition = build(
        journal=journal, require_journal=True
    )

    def failing_append(_record):
        raise RuntimeError("forced journal failure")

    journal.append = failing_append  # type: ignore[method-assign]

    composition.start(
        (
            underlying(
                "NSE:NIFTY50-INDEX",
                resolution_id="res-u",
                canonical_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
            ),
        )
    )
    assert streaming.wait_until_connected(1.0)
    factory.socket.emit(
        {"symbol": "NSE:NIFTY50-INDEX", "ltp": 23456.75}
    )

    health = composition.journal_health()
    assert health.configured is True
    assert health.required is True
    assert health.healthy is False
    assert health.append_failures == 1
    assert len(health.unjournaled_observation_ids) == 1
    streaming.close()


def test_require_journal_without_journal_is_rejected():
    import pytest

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
    with pytest.raises(Exception):
        X1DataPlaneCompositionV1(
            hub=hub,
            tracker=tracker,
            streaming=streaming,
            consumer_id="x",
            journal=None,
            require_journal=True,
        )
    streaming.close()


def test_result_history_is_bounded():
    factory, streaming, hub, composition = build(
        max_result_history=3
    )
    prev = underlying(
        "NSE:NIFTY50-INDEX",
        resolution_id="res-u",
        canonical_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)

    for i in range(6):
        factory.socket.emit(
            {"symbol": "NSE:NIFTY50-INDEX", "ltp": 100.0 + i}
        )

    assert len(composition.results()) == 3
    streaming.close()


def test_rollover_history_is_bounded():
    factory, streaming, hub, composition = build(
        max_rollover_history=2
    )
    prev = underlying(
        "NSE:NIFTY50-INDEX",
        resolution_id="res-u",
        canonical_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
    )
    composition.start((prev,))
    assert streaming.wait_until_connected(1.0)

    for _ in range(4):
        composition.rollover(
            previous_instrument=prev,
            resolver=ScriptedResolver([prev]),
            as_of=BASE,
        )

    assert len(composition.rollover_history()) == 2
    streaming.close()
