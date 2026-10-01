from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.contracts.market_data_v2 import (
    MarketDataProvenanceV2,
    MarketQuoteV2,
)
from services.x1.instrument_rollover_v2 import (
    InstrumentRolloverError,
    InstrumentRolloverResultV2,
    InstrumentRolloverStatusV2,
    invalidate_from_rollover_v2,
    resolve_instrument_replacement_v2,
)

AS_OF = datetime(2026, 9, 30, 16, 0, tzinfo=UTC)


def previous_instrument(
    *,
    kind="FUTURE",
    provider_symbol="NSE:NIFTY26SEPFUT",
    resolution_id="FYR_V2_OLD",
    canonical_id="NIFTY:FUTURE:2026-09-30",
    expiry="2026-09-30",
    strike=None,
    option_type=None,
    market="NIFTY",
    underlying_exchange="NSE",
    derivative_exchange="NFO",
):
    return {
        "provider": "FYERS",
        "market_symbol": market,
        "instrument_type": kind,
        "provider_symbol": provider_symbol,
        "resolution_id": resolution_id,
        "canonical_instrument_id": canonical_id,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,
        "underlying_exchange": underlying_exchange,
        "derivative_exchange": derivative_exchange,
    }


class ScriptedResolver:
    """Resolver whose behaviour is driven by a queue of scripts.

    Each call pops the next script. A script is either a mapping
    (returned) or an exception instance (raised).
    """

    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.calls = []

    def resolve(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripts:
            raise AssertionError("resolver called more than scripted.")
        script = self._scripts.pop(0)
        if isinstance(script, BaseException):
            raise script
        return script


def quote_for(previous, *, price=100.0):
    return MarketQuoteV2(
        quote_id="q1",
        market_symbol=previous["market_symbol"],
        exchange=(
            previous["underlying_exchange"]
            if previous["instrument_type"] == "UNDERLYING"
            else previous["derivative_exchange"]
        ),
        instrument_type=previous["instrument_type"],
        canonical_instrument_id=previous["canonical_instrument_id"],
        last_price=price,
        bid_price=None,
        ask_price=None,
        volume=None,
        open_interest=None,
        provenance=MarketDataProvenanceV2(
            provider="FYERS",
            provider_symbol=previous["provider_symbol"],
            provider_exchange=(
                previous["underlying_exchange"]
                if previous["instrument_type"] == "UNDERLYING"
                else previous["derivative_exchange"]
            ),
            source_type="LIVE",
            observed_at=AS_OF - timedelta(seconds=1),
            received_at=AS_OF - timedelta(seconds=1),
        ),
    )


def test_not_expired_when_same_identity_still_resolves():
    previous = previous_instrument()
    replacement = previous_instrument(
        provider_symbol="NSE:NIFTY26SEPFUT",
        resolution_id="FYR_V2_OLD",
    )
    resolver = ScriptedResolver([replacement])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous,
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.NOT_EXPIRED
    assert result.new_instrument is None
    assert len(resolver.calls) == 1


def test_replaced_when_original_fails_and_replacement_differs():
    previous = previous_instrument()
    new = previous_instrument(
        provider_symbol="NSE:NIFTY26OCTFUT",
        resolution_id="FYR_V2_NEW",
        canonical_id="NIFTY:FUTURE:2026-10-28",
        expiry="2026-10-28",
    )
    resolver = ScriptedResolver(
        [RuntimeError("expired"), new]
    )
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous,
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.REPLACED
    assert result.new_instrument is not None
    assert (
        result.new_instrument["provider_symbol"]
        == "NSE:NIFTY26OCTFUT"
    )
    assert len(resolver.calls) == 2
    assert resolver.calls[1]["expiry"] is None


def test_unavailable_when_replacement_also_fails():
    previous = previous_instrument()
    resolver = ScriptedResolver(
        [RuntimeError("expired"), RuntimeError("no replacement")]
    )
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous,
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.UNAVAILABLE
    assert result.new_instrument is None


def test_ambiguous_when_resolver_returns_same_resolution_id():
    previous = previous_instrument()
    same = previous_instrument(
        resolution_id=previous["resolution_id"],
        provider_symbol="NSE:NIFTY26SEPFUT",
    )
    resolver = ScriptedResolver([RuntimeError("expired"), same])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous,
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.AMBIGUOUS


def test_underlying_is_never_rollover_eligible():
    previous = previous_instrument(
        kind="UNDERLYING",
        provider_symbol="NSE:NIFTY50-INDEX",
        resolution_id="FYR_V2_UNDER",
        canonical_id="NIFTY:UNDERLYING",
        expiry=None,
        underlying_exchange="NSE",
        derivative_exchange="NFO",
    )
    resolver = ScriptedResolver([])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous,
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.NOT_EXPIRED
    assert result.reason_code == "underlying_has_no_expiry"
    assert resolver.calls == []


def test_invalid_as_of_returns_invalid_input():
    resolver = ScriptedResolver([])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=previous_instrument(),
        as_of=datetime(2026, 9, 30, 16, 0),  # naive
    )
    assert result.status is InstrumentRolloverStatusV2.INVALID_INPUT
    assert resolver.calls == []


def test_previous_must_be_mapping():
    resolver = ScriptedResolver([])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument=None,  # type: ignore[arg-type]
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.INVALID_INPUT


def test_previous_missing_fields_is_invalid():
    resolver = ScriptedResolver([])
    result = resolve_instrument_replacement_v2(
        resolver=resolver,
        previous_instrument={"market_symbol": "NIFTY"},
        as_of=AS_OF,
    )
    assert result.status is InstrumentRolloverStatusV2.INVALID_INPUT
    assert (
        result.reason_code == "previous_instrument_missing_fields"
    )


def test_invalidate_from_rollover_noop_when_not_replaced():
    hub = SharedMarketDataHubV2()
    previous = previous_instrument()
    hub.publish_quote(quote_for(previous, price=100.0))
    result = InstrumentRolloverResultV2(
        status=InstrumentRolloverStatusV2.NOT_EXPIRED,
        previous_resolution_id=previous["resolution_id"],
        previous_provider_symbol=previous["provider_symbol"],
        new_instrument=None,
        reason_code=None,
    )
    counts = invalidate_from_rollover_v2(
        hub=hub,
        previous_instrument=previous,
        rollover=result,
    )
    assert counts == {"quotes": 0, "depth": 0, "candle_series": 0}
    assert hub.snapshot_counts()["quotes"] == 1


def test_invalidate_from_rollover_removes_affected_quote():
    hub = SharedMarketDataHubV2()
    previous = previous_instrument()
    hub.publish_quote(quote_for(previous, price=100.0))
    assert hub.snapshot_counts()["quotes"] == 1
    result = InstrumentRolloverResultV2(
        status=InstrumentRolloverStatusV2.REPLACED,
        previous_resolution_id=previous["resolution_id"],
        previous_provider_symbol=previous["provider_symbol"],
        new_instrument=previous_instrument(
            provider_symbol="NSE:NIFTY26OCTFUT",
            resolution_id="FYR_V2_NEW",
        ),
        reason_code=None,
    )
    counts = invalidate_from_rollover_v2(
        hub=hub,
        previous_instrument=previous,
        rollover=result,
    )
    assert counts["quotes"] == 1
    assert hub.snapshot_counts()["quotes"] == 0


def test_invalidate_does_not_touch_other_provider():
    # Both quotes use the same provider FYERS so that the isolation
    # boundary we are testing is instrument identity, not provider
    # identity. The hub keys on (provider, market, exchange,
    # instrument_type, canonical_id), so two distinct canonical IDs
    # produce two distinct entries.
    hub = SharedMarketDataHubV2()
    previous = previous_instrument()
    other = previous_instrument(
        provider_symbol="NSE:NIFTY26OCTFUT",
        resolution_id="FYR_V2_OTHER",
        canonical_id="NIFTY:FUTURE:2026-10-28",
        expiry="2026-10-28",
    )
    hub.publish_quote(quote_for(previous, price=100.0))
    hub.publish_quote(quote_for(other, price=200.0))
    assert hub.snapshot_counts()["quotes"] == 2
    result = InstrumentRolloverResultV2(
        status=InstrumentRolloverStatusV2.REPLACED,
        previous_resolution_id=previous["resolution_id"],
        previous_provider_symbol=previous["provider_symbol"],
        new_instrument=other,
        reason_code=None,
    )
    counts = invalidate_from_rollover_v2(
        hub=hub,
        previous_instrument=previous,
        rollover=result,
    )
    assert counts["quotes"] == 1
    assert hub.snapshot_counts()["quotes"] == 1
    # Verify the survivor is the other canonical instrument, not a
    # corrupted leftover of the invalidated one.
    remaining = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NFO",
        instrument_type="FUTURE",
        canonical_instrument_id="NIFTY:FUTURE:2026-10-28",
        max_age_seconds=3600,
        now=AS_OF,
    )
    assert remaining.last_price == 200.0


def test_invalidate_rejects_bad_hub():
    with pytest.raises(InstrumentRolloverError):
        invalidate_from_rollover_v2(
            hub=None,  # type: ignore[arg-type]
            previous_instrument=previous_instrument(),
            rollover=InstrumentRolloverResultV2(
                status=InstrumentRolloverStatusV2.REPLACED,
                previous_resolution_id="x",
                previous_provider_symbol="y",
                new_instrument=None,
                reason_code=None,
            ),
        )


def test_invalidate_rejects_bad_previous_instrument():
    hub = SharedMarketDataHubV2()
    with pytest.raises(InstrumentRolloverError):
        invalidate_from_rollover_v2(
            hub=hub,
            previous_instrument={"market_symbol": "NIFTY"},
            rollover=InstrumentRolloverResultV2(
                status=InstrumentRolloverStatusV2.REPLACED,
                previous_resolution_id="x",
                previous_provider_symbol="y",
                new_instrument=None,
                reason_code=None,
            ),
        )
