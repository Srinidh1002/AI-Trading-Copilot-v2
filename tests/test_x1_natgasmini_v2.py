"""X1-focused NATGASMINI coverage.

Exercises the F8 resolver, the F8 symbol master parser, and the X1
bridge/tracker end-to-end against a NATGASMINI fixture. This is the
market that was not explicitly covered in the original X1 test set.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
    FyersResolutionError,
)
from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterIndexV2,
    parse_master_record_v2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.x1.observation_tracker_v1 import (
    ObservationQualityV1,
    ObservationTrackerV1,
)
from services.x1.streaming_hub_bridge_v1 import (
    StreamingHubBridgeV1,
)

BASE = datetime(2026, 9, 15, 9, 15, tzinfo=UTC)


NATGASMINI_ROWS = [
    {
        "symbol": "MCX:NATGASMINI",
        "exch": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "COMMODITY",
        "underlying_symbol": "NATGASMINI",
    },
    {
        "symbol": "MCX:NATGASMINI26SEPFUT",
        "exch": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "FUT",
        "underlying_symbol": "NATGASMINI",
        "expiry": "2026-09-30",
        "fyToken": "NG1",
        "lot_size": "1250",
        "tick_size": "0.10",
    },
    {
        "symbol": "MCX:NATGASMINI26OCTFUT",
        "exch": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "FUT",
        "underlying_symbol": "NATGASMINI",
        "expiry": "2026-10-31",
        "fyToken": "NG2",
        "lot_size": "1250",
        "tick_size": "0.10",
    },
    {
        "symbol": "MCX:NATGASMINI26AUGFUT",
        "exch": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "FUT",
        "underlying_symbol": "NATGASMINI",
        "expiry": "2026-08-31",
        "fyToken": "NGX",
        "lot_size": "1250",
        "tick_size": "0.10",
    },
]


class _Store:
    def __init__(self, rows):
        self._idx = FyersSymbolMasterIndexV2.from_rows(
            rows, "MCX_COM"
        )

    def get_index(self, segment):
        if segment != "MCX_COM":
            raise RuntimeError("segment not cached: " + segment)
        return self._idx


class _Client:
    def futures_chain(self, data):
        del data
        return {"s": "error", "message": "no chain for MCX"}


def _resolver():
    return FyersFiveMarketInstrumentResolverV2(
        data_client=_Client(),
        master_store=_Store(NATGASMINI_ROWS),
        clock=lambda: BASE,
    )


def test_master_parser_classifies_natgasmini_future_without_optype():
    rec = parse_master_record_v2(
        NATGASMINI_ROWS[1], default_segment="MCX_COM"
    )
    assert rec is not None
    assert rec.instrument_kind == "FUTURE"
    assert rec.underlying_symbol == "NATGASMINI"
    assert rec.expiry == date(2026, 9, 30)
    assert rec.lot_size == 1250


def test_master_parser_classifies_natgasmini_underlying():
    rec = parse_master_record_v2(
        NATGASMINI_ROWS[0], default_segment="MCX_COM"
    )
    assert rec is not None
    assert rec.instrument_kind == "UNDERLYING"


def test_master_parser_rejects_natgasmini_future_without_expiry():
    bad = {
        "symbol": "MCX:NATGASMINI_BADFUT",
        "exch": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "FUT",
        "underlying_symbol": "NATGASMINI",
        "fyToken": "NG_BAD",
        "lot_size": "1250",
        "tick_size": "0.10",
    }
    rec = parse_master_record_v2(bad, default_segment="MCX_COM")
    assert rec is None


def test_resolver_natgasmini_underlying_from_master():
    result = _resolver().resolve(
        market_symbol="NATGASMINI",
        instrument_type="UNDERLYING",
        as_of=BASE,
    )
    assert result["provider"] == "FYERS"
    assert result["provider_symbol"] == "MCX:NATGASMINI"
    assert result["instrument_type"] == "UNDERLYING"
    assert result["data_only"] is True
    assert result["execution_mode"] == "PAPER"
    assert result["live_execution_eligible"] is False


def test_resolver_natgasmini_front_future():
    result = _resolver().resolve(
        market_symbol="NATGASMINI",
        instrument_type="FUTURE",
        as_of=BASE,
    )
    assert result["provider_symbol"] == "MCX:NATGASMINI26SEPFUT"
    assert result["expiry"] == "2026-09-30"
    assert result["lot_size"] == 1250
    assert result["contract_metadata_status"] == "VERIFIED"


def test_resolver_natgasmini_expired_future_is_skipped():
    # Ask as of a date after the first future's expiry.
    after_first = datetime(2026, 10, 1, 9, 15, tzinfo=UTC)
    result = _resolver().resolve(
        market_symbol="NATGASMINI",
        instrument_type="FUTURE",
        as_of=after_first,
    )
    assert result["provider_symbol"] == "MCX:NATGASMINI26OCTFUT"
    assert result["expiry"] == "2026-10-31"


def test_resolver_natgasmini_all_expired_fails_closed():
    after_all = datetime(2026, 12, 1, 9, 15, tzinfo=UTC)
    with pytest.raises(FyersResolutionError):
        _resolver().resolve(
            market_symbol="NATGASMINI",
            instrument_type="FUTURE",
            as_of=after_all,
        )


def test_resolver_natgasmini_same_day_expiry_fails_closed():
    # MCX same-day expiry is conservatively refused.
    same_day = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
    with pytest.raises(FyersResolutionError):
        _resolver().resolve(
            market_symbol="NATGASMINI",
            instrument_type="FUTURE",
            as_of=same_day,
            expiry=date(2026, 9, 30),
        )


def test_resolver_natgasmini_missing_master_fails_closed():
    class _EmptyStore:
        def get_index(self, segment):
            raise RuntimeError("master not cached")

    resolver = FyersFiveMarketInstrumentResolverV2(
        data_client=_Client(),
        master_store=_EmptyStore(),
        clock=lambda: BASE,
    )
    with pytest.raises(FyersResolutionError):
        resolver.resolve(
            market_symbol="NATGASMINI",
            instrument_type="FUTURE",
            as_of=BASE,
        )


def test_resolver_natgasmini_invalid_instrument_type_fails_closed():
    with pytest.raises(FyersResolutionError):
        _resolver().resolve(
            market_symbol="NATGASMINI",
            instrument_type="SWAP",
            as_of=BASE,
        )


def test_resolver_natgasmini_naive_as_of_fails_closed():
    with pytest.raises(FyersResolutionError):
        _resolver().resolve(
            market_symbol="NATGASMINI",
            instrument_type="FUTURE",
            as_of=datetime(2026, 9, 15, 9, 15),
        )


def test_resolver_natgasmini_rejects_derivative_args_on_underlying():
    with pytest.raises(FyersResolutionError):
        _resolver().resolve(
            market_symbol="NATGASMINI",
            instrument_type="UNDERLYING",
            as_of=BASE,
            strike=100.0,
        )


def test_x1_bridge_publishes_natgasmini_future_into_hub():
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bridge = StreamingHubBridgeV1(hub=hub, tracker=tracker)

    record = {
        "provider": "FYERS",
        "provider_symbol": "MCX:NATGASMINI26SEPFUT",
        "ltp": 253.7,
        "ts": BASE,
        "received_at": BASE,
        "timestamp_source": "PROVIDER",
        "canonical_instrument_id": (
            "NATGASMINI|FUTURE|MCX:NATGASMINI26SEPFUT"
        ),
        "market_symbol": "NATGASMINI",
        "instrument_type": "FUTURE",
        "connection_generation": 1,
    }

    result = bridge.handle_observation(
        record, connection_generation=1, current_generation=1
    )
    assert result.accepted is True
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NATGASMINI",
        exchange="MCX",
        instrument_type="FUTURE",
        canonical_instrument_id=(
            "NATGASMINI|FUTURE|MCX:NATGASMINI26SEPFUT"
        ),
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 253.7


def test_x1_tracker_rejects_duplicate_natgasmini_tick():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    record = {
        "provider": "FYERS",
        "provider_symbol": "MCX:NATGASMINI26SEPFUT",
        "ltp": 253.7,
        "ts": BASE,
        "received_at": BASE,
        "timestamp_source": "PROVIDER",
        "canonical_instrument_id": (
            "NATGASMINI|FUTURE|MCX:NATGASMINI26SEPFUT"
        ),
        "market_symbol": "NATGASMINI",
        "instrument_type": "FUTURE",
        "connection_generation": 1,
    }
    first = tracker.classify(
        record, connection_generation=1, current_generation=1
    )
    second = tracker.classify(
        record, connection_generation=1, current_generation=1
    )
    assert first.quality is ObservationQualityV1.VALID
    assert (
        second.quality is ObservationQualityV1.SUSPECTED_DUPLICATE
    )


def test_x1_tracker_classifies_natgasmini_silence_per_instrument():
    tracker = ObservationTrackerV1(
        clock=lambda: BASE + timedelta(seconds=120),
        stale_after_seconds=30.0,
    )
    # No tick ever seen for this instrument: NO_TICK_YET regardless of
    # elapsed wall time.
    report = tracker.silence_report(
        "NATGASMINI|FUTURE|MCX:NATGASMINI26SEPFUT",
        market_symbol="NATGASMINI",
    )
    assert report.state.value == "NO_TICK_YET"
