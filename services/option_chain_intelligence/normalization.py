"""Provider-neutral normalization of already-supplied option-chain records.

This module deliberately accepts a small canonical mapping vocabulary.  It
does not know how a provider represented the source response, fetch data, or
retain provider-specific payloads.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
import math


# The complete, provider-neutral vocabulary accepted for each supplied record.
# Extra mapping keys are intentionally ignored and are never retained.
CANONICAL_OPTION_CHAIN_RECORD_KEYS = (
    "strike",
    "option_type",
    "ltp",
    "bid_price",
    "ask_price",
    "bid_quantity",
    "ask_quantity",
    "volume",
    "open_interest",
    "change_in_open_interest",
    "implied_volatility",
    "underlying_value",
    "source_record_id",
    "is_complete",
)

_PRICE_KEYS = (
    "ltp",
    "bid_price",
    "ask_price",
    "implied_volatility",
    "underlying_value",
)
_INTEGER_KEYS = (
    "bid_quantity",
    "ask_quantity",
    "volume",
    "open_interest",
)
_SIGNED_INTEGER_KEYS = ("change_in_open_interest",)


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _is_finite_number(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _is_exact_supported_identity(symbol: object, exchange: object) -> bool:
    # Importing the shared registry only when normalization is invoked keeps
    # this module import-isolated and avoids package initialization side effects.
    from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES

    return isinstance(symbol, str) and isinstance(exchange, str) and (symbol, exchange) in SUPPORTED_MARKET_IDENTITIES


def _validate_factory(factory: object, name: str) -> None:
    if factory is not None and not callable(factory):
        raise ValueError(f"{name} must be callable when supplied.")


def _resolve_clock(clock: Callable[[], datetime] | None) -> datetime:
    if clock is not None and not callable(clock):
        raise ValueError("clock must be callable when supplied.")
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if not _is_aware(value):
        raise ValueError("clock must return a timezone-aware datetime.")
    return value


def _validate_record(record: Mapping[str, object]) -> None:
    if not set(CANONICAL_OPTION_CHAIN_RECORD_KEYS).issubset(record):
        raise ValueError("Option-chain record is missing canonical keys.")
    if not _is_finite_number(record["strike"], positive=True):
        raise ValueError("Option-chain record strike must be finite and positive.")
    if record["option_type"] not in {"CALL", "PUT"}:
        raise ValueError("Option-chain record option_type must be CALL or PUT.")
    for key in _PRICE_KEYS:
        value = record[key]
        if value is not None and not _is_finite_number(value):
            raise ValueError(f"Option-chain record {key} must be finite and non-negative.")
    for key in _INTEGER_KEYS:
        value = record[key]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise ValueError(f"Option-chain record {key} must be a non-negative integer.")
    for key in _SIGNED_INTEGER_KEYS:
        value = record[key]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"Option-chain record {key} must be an integer when supplied.")
    record_id = record["source_record_id"]
    if record_id is not None and (not isinstance(record_id, str) or not record_id.strip()):
        raise ValueError("Option-chain source_record_id must be a non-empty string or None.")
    if not isinstance(record["is_complete"], bool):
        raise ValueError("Option-chain record is_complete must be bool.")


def _validate_normalization_inputs(
    *,
    underlying_symbol: object,
    exchange: object,
    expiry: object,
    underlying_value: object,
    source_timestamp: object,
    provider_name: object,
    records: object,
    option_quote_id_factory: object = None,
    strike_row_id_factory: object = None,
    option_chain_snapshot_id_factory: object = None,
) -> tuple[Mapping[str, object], ...]:
    """Validate normalization inputs without acquiring a clock value.

    The pipeline uses this private helper before its single shared clock call.
    """
    if not _is_exact_supported_identity(underlying_symbol, exchange):
        raise ValueError("Option-chain identity must be an exact supported market identity.")
    if not isinstance(expiry, date) or isinstance(expiry, datetime):
        raise ValueError("expiry must be a date.")
    if underlying_value is not None and not _is_finite_number(underlying_value, positive=True):
        raise ValueError("underlying_value must be finite and positive when supplied.")
    if not _is_aware(source_timestamp):
        raise ValueError("source_timestamp must be timezone-aware.")
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise ValueError("provider_name must be a non-empty string.")
    if not isinstance(records, tuple) or not all(isinstance(record, Mapping) for record in records):
        raise ValueError("records must be an explicit tuple of mappings.")
    _validate_factory(option_quote_id_factory, "option_quote_id_factory")
    _validate_factory(strike_row_id_factory, "strike_row_id_factory")
    _validate_factory(option_chain_snapshot_id_factory, "option_chain_snapshot_id_factory")
    for record in records:
        _validate_record(record)
    return records


def _default_factory(prefix: str) -> Callable[[], str]:
    count = 0

    def build() -> str:
        nonlocal count
        count += 1
        return f"{prefix}-{count}"

    return build


def _next_id(factory: Callable[[], object], label: str) -> str:
    value = factory()
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} factory must return a non-empty string.")
    return value


def _record_sort_key(record: Mapping[str, object]) -> tuple[object, ...]:
    # A canonical ordering makes factories and normalized rows deterministic
    # even when a provider supplies rows in an arbitrary order.
    return (
        float(record["strike"]),
        0 if record["option_type"] == "CALL" else 1,
        record["source_record_id"] or "",
        *("" if record[key] is None else str(record[key]) for key in CANONICAL_OPTION_CHAIN_RECORD_KEYS[:-2]),
    )


def _strike_token(strike: object) -> str:
    return format(float(strike), ".12g")


def normalize_option_chain_records(
    *,
    underlying_symbol,
    exchange,
    expiry,
    underlying_value,
    source_timestamp,
    provider_name,
    records,
    clock=None,
    option_quote_id_factory=None,
    strike_row_id_factory=None,
    option_chain_snapshot_id_factory=None,
):
    """Build an immutable normalized option-chain snapshot from canonical rows.

    No aliases, provider payloads, quote fetching, strike-interval inference, or
    synthetic missing CALL/PUT sides are used here.  Duplicate sides retain the
    first canonical record in sorted order and are recorded as bounded snapshot
    warnings for the quality stage.
    """
    records = _validate_normalization_inputs(
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        expiry=expiry,
        underlying_value=underlying_value,
        source_timestamp=source_timestamp,
        provider_name=provider_name,
        records=records,
        option_quote_id_factory=option_quote_id_factory,
        strike_row_id_factory=strike_row_id_factory,
        option_chain_snapshot_id_factory=option_chain_snapshot_id_factory,
    )
    now = _resolve_clock(clock)

    # Contracts are imported only after the input boundary is validated.
    from services.contracts import OptionChainSnapshotV1, OptionQuoteV1, OptionStrikeRowV1

    quote_factory = option_quote_id_factory or _default_factory("option-quote")
    row_factory = strike_row_id_factory or _default_factory("option-strike-row")
    snapshot_factory = option_chain_snapshot_id_factory or _default_factory("option-chain-snapshot")

    selected: dict[tuple[float, str], Mapping[str, object]] = {}
    duplicate_warnings: list[str] = []
    duplicate_counts: dict[tuple[float, str], int] = {}
    for record in sorted(records, key=_record_sort_key):
        key = (float(record["strike"]), str(record["option_type"]))
        if key in selected:
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
            duplicate_warnings.append(
                f"duplicate_option_side:{_strike_token(key[0])}:{key[1]}:{duplicate_counts[key]}"
            )
            continue
        selected[key] = record

    quote_by_side: dict[tuple[float, str], object] = {}
    for (strike, option_type), record in selected.items():
        crossed = record["bid_price"] is not None and record["ask_price"] is not None and record["bid_price"] > record["ask_price"]
        quote_by_side[(strike, option_type)] = OptionQuoteV1(
            option_quote_id=_next_id(quote_factory, "option_quote_id"),
            created_at=now,
            underlying_symbol=underlying_symbol,
            exchange=exchange,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            ltp=record["ltp"],
            bid_price=record["bid_price"],
            ask_price=record["ask_price"],
            bid_quantity=record["bid_quantity"],
            ask_quantity=record["ask_quantity"],
            volume=record["volume"],
            open_interest=record["open_interest"],
            change_in_open_interest=record["change_in_open_interest"],
            implied_volatility=record["implied_volatility"],
            underlying_value=record["underlying_value"],
            source_timestamp=source_timestamp,
            is_complete=record["is_complete"],
            provider_name=provider_name,
            source_record_id=record["source_record_id"],
            blockers=(),
            warnings=("crossed_market",) if crossed else (),
            execution_mode="PAPER",
            live_execution_eligible=False,
        )

    rows = []
    for strike in sorted({key[0] for key in quote_by_side}):
        call = quote_by_side.get((strike, "CALL"))
        put = quote_by_side.get((strike, "PUT"))
        rows.append(
            OptionStrikeRowV1(
                strike_row_id=_next_id(row_factory, "strike_row_id"),
                underlying_symbol=underlying_symbol,
                exchange=exchange,
                expiry=expiry,
                strike=strike,
                call=call,
                put=put,
                blockers=(),
                warnings=(),
            )
        )

    strike_rows = tuple(rows)
    complete_pair_count = sum(row.call is not None and row.put is not None for row in strike_rows)
    call_only_count = sum(row.call is not None and row.put is None for row in strike_rows)
    put_only_count = sum(row.call is None and row.put is not None for row in strike_rows)
    snapshot_blockers = ("empty_option_chain",) if not strike_rows else ()
    return OptionChainSnapshotV1(
        option_chain_snapshot_id=_next_id(snapshot_factory, "option_chain_snapshot_id"),
        created_at=now,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        expiry=expiry,
        underlying_value=underlying_value,
        strike_rows=strike_rows,
        strike_count=len(strike_rows),
        complete_pair_count=complete_pair_count,
        call_only_count=call_only_count,
        put_only_count=put_only_count,
        minimum_strike=strike_rows[0].strike if strike_rows else None,
        maximum_strike=strike_rows[-1].strike if strike_rows else None,
        source_timestamp=source_timestamp,
        provider_name=provider_name,
        blockers=snapshot_blockers,
        warnings=tuple(dict.fromkeys(duplicate_warnings)),
        execution_mode="PAPER",
        live_execution_eligible=False,
    )
