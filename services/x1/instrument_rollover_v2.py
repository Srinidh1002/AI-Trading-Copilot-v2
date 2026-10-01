"""Controlled data-subscription rollover for X1.

Scope: **data subscription only**. Trading-position rollover is a
different responsibility owned by the PAPER runtime and is never
touched here.

Behaviour:

* Given a previous provider instrument mapping and a resolver, decide
  whether the previous contract is still valid at ``as_of``.
* If still valid, return ``NOT_EXPIRED`` and do nothing.
* If expired and a unique replacement exists, return ``REPLACED`` with
  the new instrument mapping. The caller is responsible for subscribing
  to the new instrument and for calling ``invalidate_from_rollover_v2``
  to clear the affected hub entries.
* If the resolver cannot unambiguously produce a replacement, fail
  closed: ``UNAVAILABLE`` or ``AMBIGUOUS``.

Invariants enforced:

* Underlyings are never rollover-eligible.
* The previous instrument mapping is never mutated.
* The resolver is never modified.
* No order, execution, decision, risk, position, broker, or
  certification capability exists here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)


class _Resolver(Protocol):
    def resolve(
        self,
        *,
        market_symbol: str,
        instrument_type: str,
        as_of: datetime | None = None,
        expiry: Any = None,
        strike: float | None = None,
        option_type: str | None = None,
    ) -> Mapping[str, Any]: ...


class InstrumentRolloverError(RuntimeError):
    """Rollover configuration failure."""


class InstrumentRolloverStatusV2(StrEnum):
    NOT_EXPIRED = "NOT_EXPIRED"
    REPLACED = "REPLACED"
    UNAVAILABLE = "UNAVAILABLE"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True, slots=True)
class InstrumentRolloverResultV2:
    status: InstrumentRolloverStatusV2
    previous_resolution_id: str
    previous_provider_symbol: str
    new_instrument: Mapping[str, Any] | None
    reason_code: str | None


def _aware_utc(name: str, value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise InstrumentRolloverError(
            f"{name} must be a timezone-aware datetime."
        )
    return value.astimezone(UTC)


def _previous_identity(
    previous: Mapping[str, Any],
) -> tuple[str, str, str, str, Any, Any, Any, str, str] | None:
    try:
        market = previous["market_symbol"]
        kind = previous["instrument_type"]
        provider_symbol = previous["provider_symbol"]
        resolution_id = previous["resolution_id"]
        canonical_id = previous["canonical_instrument_id"]
    except (KeyError, TypeError):
        return None
    if not all(
        isinstance(v, str) and v.strip()
        for v in (
            market,
            kind,
            provider_symbol,
            resolution_id,
            canonical_id,
        )
    ):
        return None
    expiry = previous.get("expiry")
    strike = previous.get("strike")
    option_type = previous.get("option_type")
    return (
        market,
        kind,
        provider_symbol,
        resolution_id,
        expiry,
        strike,
        option_type,
        canonical_id,
        resolution_id,
    )


def resolve_instrument_replacement_v2(
    *,
    resolver: _Resolver,
    previous_instrument: Mapping[str, Any],
    as_of: datetime,
) -> InstrumentRolloverResultV2:
    """Determine whether a data subscription needs replacing.

    Never mutates state. Never raises on ordinary rollover conditions.
    """
    try:
        as_of_dt = _aware_utc("as_of", as_of)
    except InstrumentRolloverError as exc:
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.INVALID_INPUT,
            previous_resolution_id="",
            previous_provider_symbol="",
            new_instrument=None,
            reason_code=str(exc),
        )

    if not isinstance(previous_instrument, Mapping):
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.INVALID_INPUT,
            previous_resolution_id="",
            previous_provider_symbol="",
            new_instrument=None,
            reason_code="previous_instrument_must_be_mapping",
        )

    identity = _previous_identity(previous_instrument)
    if identity is None:
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.INVALID_INPUT,
            previous_resolution_id="",
            previous_provider_symbol="",
            new_instrument=None,
            reason_code="previous_instrument_missing_fields",
        )

    (
        market,
        kind,
        provider_symbol,
        resolution_id,
        expiry,
        strike,
        option_type,
        _canonical_id,
        _echo_resolution,
    ) = identity

    if kind == "UNDERLYING":
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.NOT_EXPIRED,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code="underlying_has_no_expiry",
        )

    try:
        resolver.resolve(
            market_symbol=market,
            instrument_type=kind,
            as_of=as_of_dt,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed, classify below
        original_error = exc
    else:
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.NOT_EXPIRED,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code=None,
        )

    # Original identity no longer resolvable. Ask the resolver to choose
    # the nearest valid replacement for the same canonical identity.
    try:
        replacement = resolver.resolve(
            market_symbol=market,
            instrument_type=kind,
            as_of=as_of_dt,
            expiry=None,
            strike=strike if kind == "OPTION" else None,
            option_type=option_type if kind == "OPTION" else None,
        )
    except Exception:  # noqa: BLE001 - classify as unavailable
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.UNAVAILABLE,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code=f"replacement_unresolvable:"
            f"{type(original_error).__name__}",
        )

    if not isinstance(replacement, Mapping):
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.UNAVAILABLE,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code="replacement_not_a_mapping",
        )

    new_resolution_id = replacement.get("resolution_id")
    new_provider_symbol = replacement.get("provider_symbol")
    if (
        not isinstance(new_resolution_id, str)
        or not isinstance(new_provider_symbol, str)
    ):
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.UNAVAILABLE,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code="replacement_missing_identity",
        )

    if new_resolution_id == resolution_id:
        # The resolver returned the same instrument that just failed
        # to resolve. That is inconsistent and must fail closed.
        return InstrumentRolloverResultV2(
            status=InstrumentRolloverStatusV2.AMBIGUOUS,
            previous_resolution_id=resolution_id,
            previous_provider_symbol=provider_symbol,
            new_instrument=None,
            reason_code="resolver_returned_same_resolution_id",
        )

    return InstrumentRolloverResultV2(
        status=InstrumentRolloverStatusV2.REPLACED,
        previous_resolution_id=resolution_id,
        previous_provider_symbol=provider_symbol,
        new_instrument=dict(replacement),
        reason_code=None,
    )


def invalidate_from_rollover_v2(
    *,
    hub: SharedMarketDataHubV2,
    previous_instrument: Mapping[str, Any],
    rollover: InstrumentRolloverResultV2,
) -> dict[str, int]:
    """Invalidate the previous instrument's cached data on REPLACED.

    No-op for every other rollover status.
    """
    if not isinstance(hub, SharedMarketDataHubV2):
        raise InstrumentRolloverError(
            "hub must be SharedMarketDataHubV2."
        )
    if not isinstance(rollover, InstrumentRolloverResultV2):
        raise InstrumentRolloverError(
            "rollover must be InstrumentRolloverResultV2."
        )
    if (
        rollover.status
        is not InstrumentRolloverStatusV2.REPLACED
    ):
        return {"quotes": 0, "depth": 0, "candle_series": 0}
    if not isinstance(previous_instrument, Mapping):
        raise InstrumentRolloverError(
            "previous_instrument must be a mapping."
        )

    provider = previous_instrument.get("provider")
    market = previous_instrument.get("market_symbol")
    kind = previous_instrument.get("instrument_type")
    canonical_id = previous_instrument.get("canonical_instrument_id")
    underlying_exchange = previous_instrument.get(
        "underlying_exchange"
    )
    derivative_exchange = previous_instrument.get(
        "derivative_exchange"
    )
    if not all(
        isinstance(v, str) and v.strip()
        for v in (provider, market, kind, canonical_id)
    ):
        raise InstrumentRolloverError(
            "previous_instrument_missing_fields"
        )

    if kind == "UNDERLYING":
        exchange = underlying_exchange
    else:
        exchange = derivative_exchange
    if not isinstance(exchange, str) or not exchange.strip():
        raise InstrumentRolloverError(
            "previous_instrument_missing_exchange"
        )

    return hub.invalidate_instrument(
        provider=provider,
        market_symbol=market,
        exchange=exchange,
        instrument_type=kind,
        canonical_instrument_id=canonical_id,
    )


__all__ = [
    "InstrumentRolloverError",
    "InstrumentRolloverResultV2",
    "InstrumentRolloverStatusV2",
    "invalidate_from_rollover_v2",
    "resolve_instrument_replacement_v2",
]
