"""Pure FYERS-normalized futures candle -> X4 adapter; no network or execution.

Consumes rows returned by the existing FyersHistoricalDataProviderV2.get_candles.
The caller, not this module, owns data acquisition, session/capture verification,
and proof of quote, volume and OI semantics. Unverified OI is never promoted.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from services.x4.contracts_v1 import X4ContractV1, X4SampleV1


class ResolvedFuturesIdentityV1(Protocol):
    market_symbol: str
    instrument_type: str
    provider: str
    provider_symbol: str
    canonical_instrument_id: str
    expiry: object
    contract_metadata_status: str
    metadata_source: str | None
    resolved_at: datetime | None
    data_only: bool
    live_execution_eligible: bool


_INTERVALS: dict[str, tuple[int, str]] = {
    "1m": (60, "ONE_MINUTE"),
    "3m": (180, "THREE_MINUTE"),
    "5m": (300, "FIVE_MINUTE"),
    "10m": (600, "TEN_MINUTE"),
    "15m": (900, "FIFTEEN_MINUTE"),
    "30m": (1800, "THIRTY_MINUTE"),
    "1h": (3600, "ONE_HOUR"),
}
_PRICE_UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}


@dataclass(frozen=True, slots=True)
class X4AdaptedCandlesV1:
    contract: X4ContractV1
    samples: tuple[X4SampleV1, ...]
    as_of: datetime
    capture_id: str
    data_only: bool = True
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not self.data_only or self.live_execution_eligible:
            raise ValueError("Adapter output must remain data-only")


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _number(value: object, *, name: str, allow_zero: bool = False) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(
            f"{name} must be positive" if not allow_zero else f"{name} must be nonnegative"
        )
    return float(value)


def _timestamp(value: object) -> datetime:
    """FYERS normalized history timestamps are Unix *seconds*, bar start."""
    if type(value) is not int or not 1_000_000_000 <= value < 10_000_000_000:
        raise ValueError("Expected Unix-second candle start timestamp")
    return datetime.fromtimestamp(value, tz=UTC)


def adapt_fyers_futures_candles_v1(
    *,
    resolved: ResolvedFuturesIdentityV1,
    rows: Sequence[Mapping[str, object]],
    timeframe: str,
    session_id: str,
    as_of: datetime,
    capture_id: str,
    capture_verified: bool,
    session_verified: bool,
    timestamp_semantics_verified: bool,
    price_unit: str,
    price_unit_verified: bool,
    volume_unit_verified: bool,
    oi_unit_verified: bool,
    oi_timestamp_verified: bool,
) -> X4AdaptedCandlesV1:
    """Adapt an explicitly verified historical capture; fail closed otherwise.

    `timestamp_semantics_verified=True` means independent evidence establishes
    that each FYERS record timestamp is the *start* of a bar with the supplied
    interval. Its completion is calculated as start + interval seconds. No
    last-tick substitution, weekend filling or automatic interval guessing.

    A numeric OI field is *not* proof of its unit or observation time; the two
    OI verification flags are independent caller-supplied evidence gates.
    """
    if not _aware(as_of):
        raise ValueError("as_of must be timezone-aware")
    if timeframe not in _INTERVALS:
        raise ValueError("Unsupported or unverified candle timeframe")
    if type(rows) not in (tuple, list) or not rows:
        raise ValueError("Historical rows must be a nonempty immutable capture")
    if (
        not isinstance(session_id, str)
        or not session_id.strip()
        or session_id != session_id.strip()
    ):
        raise ValueError("A canonical session_id is required")
    if (
        not isinstance(capture_id, str)
        or not capture_id.strip()
        or capture_id != capture_id.strip()
    ):
        raise ValueError("A canonical capture_id is required")
    if not all(
        type(value) is bool
        for value in (
            capture_verified,
            session_verified,
            timestamp_semantics_verified,
            price_unit_verified,
            volume_unit_verified,
            oi_unit_verified,
            oi_timestamp_verified,
        )
    ):
        raise ValueError("Verification flags must be exact booleans")
    if not all(
        (capture_verified, session_verified, timestamp_semantics_verified, price_unit_verified)
    ):
        raise ValueError("Capture, session, candle timestamps and quote unit must be verified")
    market = getattr(resolved, "market_symbol", None)
    if market not in _PRICE_UNITS or price_unit != _PRICE_UNITS[market]:
        raise ValueError("Invalid or mismatched price unit for canonical market")
    if (
        getattr(resolved, "provider", None) != "FYERS"
        or getattr(resolved, "instrument_type", None) != "FUTURE"
        or getattr(resolved, "data_only", None) is not True
        or getattr(resolved, "live_execution_eligible", None) is not False
    ):
        raise ValueError("A FYERS data-only resolved FUTURE is required")
    provider_symbol = getattr(resolved, "provider_symbol", None)
    contract_id = getattr(resolved, "canonical_instrument_id", None)
    metadata_source = getattr(resolved, "metadata_source", None)
    if not all(
        isinstance(v, str) and v.strip() == v and v
        for v in (provider_symbol, contract_id, metadata_source)
    ):
        raise ValueError("Resolved contract identity and metadata provenance are required")
    resolved_at = getattr(resolved, "resolved_at", None)
    if resolved_at is not None and (not _aware(resolved_at) or resolved_at > as_of):
        raise ValueError("Future-dated or naive instrument resolution violates historical as_of")
    metadata_status = getattr(resolved, "contract_metadata_status", None)
    if metadata_status not in ("VERIFIED", "PROVISIONAL", "UNAVAILABLE"):
        raise ValueError("Unknown instrument metadata status")
    contract = X4ContractV1(
        market=market,
        canonical_instrument_id=contract_id,
        provider="FYERS",
        provider_symbol=provider_symbol,
        expiry=resolved.expiry,
        price_unit=price_unit,
        metadata_status=metadata_status,
        metadata_source=metadata_source,
    )
    seconds, long_interval = _INTERVALS[timeframe]
    normalized = []
    prev_end: datetime | None = None
    for record in rows:
        if not isinstance(record, Mapping):
            raise ValueError("A normalized candle must be a mapping")
        if record.get("provider") != "FYERS" or record.get("provider_symbol") != provider_symbol:
            raise ValueError("Mixed provider symbol or futures contract")
        if record.get("interval") not in (timeframe, long_interval):
            raise ValueError("Mixed or mismatched timeframe")
        start = _timestamp(record.get("timestamp"))
        end = start + timedelta(seconds=seconds)
        if end > as_of:
            raise ValueError("Unclosed or future candle cannot enter historical analysis")
        if prev_end is not None and start < prev_end:
            raise ValueError("Overlapping, duplicate or out-of-order candles")
        prev_end = end
        open_ = _number(record.get("open"), name="open")
        high = _number(record.get("high"), name="high")
        low = _number(record.get("low"), name="low")
        close = _number(record.get("close"), name="close")
        if not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError("Invalid candle OHLC range")
        raw_vol = record.get("volume")
        volume = _number(raw_vol, name="volume", allow_zero=True) if raw_vol is not None else None
        raw_oi = record.get("open_interest")
        oi = _number(raw_oi, name="open_interest") if raw_oi is not None else None
        normalized.append(
            X4SampleV1(
                contract_id=contract_id,
                session_id=session_id,
                timeframe=timeframe,
                observed_at=end,
                source_id=f"{capture_id}:{start.isoformat()}",
                close=close,
                high=high,
                low=low,
                volume=volume,
                open_interest=oi,
                volume_verified=volume_unit_verified and volume is not None,
                oi_verified=(oi_unit_verified and oi_timestamp_verified and oi is not None),
                is_closed=True,
                quality="VALID",
            )
        )
    return X4AdaptedCandlesV1(contract, tuple(normalized), as_of, capture_id)
