"""Immutable X5 option-chain observations and provenance; no provider or broker I/O."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from hashlib import sha256

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_EXCHANGES = {
    "NIFTY": ("NFO", "NSE:"),
    "SENSEX": ("BFO", "BSE:"),
    "CRUDEOILM": ("MCX", "MCX:"),
    "GOLDM": ("MCX", "MCX:"),
    "NATGASMINI": ("MCX", "MCX:"),
}
METADATA_STATUSES = frozenset({"VERIFIED", "PROVISIONAL", "UNAVAILABLE"})


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _finite(value: object, *, positive: bool = False, signed: bool = False) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and (not positive or value > 0)
        and (signed or value >= 0)
    )


def _encode(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    return value


def canonical_sha256(value: object) -> str:
    return sha256(
        json.dumps(_encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class X5ContractV1:
    """Canonical five-market identity. VERIFIED is supplied evidence, not inferred."""

    market: str
    provider: str
    underlying_provider_symbol: str
    option_exchange: str
    expiry: date
    expiry_source_id: str
    metadata_status: str
    metadata_source: str
    schema_version: str = "X5_OPTION_CONTRACT_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKET_EXCHANGES:
            raise ValueError("Unsupported X5 market")
        expected_exchange, _ = MARKET_EXCHANGES[self.market]
        if self.provider != "FYERS" or self.option_exchange != expected_exchange:
            raise ValueError("Provider or option exchange does not match the market")
        required_root = {
            "NIFTY": "NSE:NIFTY50-INDEX",
            "SENSEX": "BSE:SENSEX-INDEX",
            "CRUDEOILM": "MCX:CRUDEOILM",
            "GOLDM": "MCX:GOLDM",
            "NATGASMINI": "MCX:NATGASMINI",
        }[self.market]
        if not _text(self.underlying_provider_symbol) or (
            self.underlying_provider_symbol != required_root
            if self.option_exchange != "MCX"
            else not self.underlying_provider_symbol.startswith(required_root)
        ):
            raise ValueError("Invalid underlying provider identity")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("Expiry must be a date")
        if not _text(self.expiry_source_id) or not _text(self.metadata_source):
            raise ValueError("Expiry and metadata provenance are required")
        if self.metadata_status not in METADATA_STATUSES:
            raise ValueError("Unknown contract metadata status")
        if (
            self.schema_version != "X5_OPTION_CONTRACT_V1"
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Contract authority must remain disabled")


@dataclass(frozen=True, slots=True)
class X5OptionObservationV1:
    """One CE or PE observation. A numeric provider field is not proof of units."""

    canonical_option_id: str
    provider_symbol: str
    option_type: str
    strike: float
    expiry: date
    observed_at: datetime
    source_record_id: str
    ltp: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    oi_unit: str | None = None
    volume_unit: str | None = None
    change_in_open_interest: float | None = None
    implied_volatility: float | None = None
    iv_unit: str | None = None
    premium_unit: str | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    oi_unit_verified: bool = False
    oi_timestamp_verified: bool = False
    volume_unit_verified: bool = False
    volume_timestamp_verified: bool = False
    premium_unit_verified: bool = False
    oi_change_verified: bool = False
    oi_change_baseline_id: str | None = None
    iv_verified: bool = False
    greeks_verified: bool = False
    schema_version: str = "X5_OPTION_OBSERVATION_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not all(
            _text(x)
            for x in (self.canonical_option_id, self.provider_symbol, self.source_record_id)
        ):
            raise ValueError("Option identity and source record are required")
        if self.option_type not in {"CE", "PE"} or not _finite(self.strike, positive=True):
            raise ValueError("Invalid CE/PE strike identity")
        if (
            not isinstance(self.expiry, date)
            or isinstance(self.expiry, datetime)
            or not _aware(self.observed_at)
        ):
            raise ValueError("Expiry and timezone-aware source timestamp are required")
        for name in (
            "ltp",
            "bid_price",
            "ask_price",
            "volume",
            "open_interest",
            "implied_volatility",
        ):
            value = getattr(self, name)
            if value is not None and not _finite(value):
                raise ValueError(f"{name} must be nonnegative and finite")
        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.ask_price < self.bid_price
        ):
            raise ValueError("Crossed bid/ask must be rejected")
        if self.change_in_open_interest is not None and not _finite(
            self.change_in_open_interest, signed=True
        ):
            raise ValueError("OI change must be signed and finite")
        if self.delta is not None and (not _finite(self.delta, signed=True) or abs(self.delta) > 1):
            raise ValueError("Delta must lie between -1 and 1")
        for name in ("gamma", "vega"):
            value = getattr(self, name)
            if value is not None and not _finite(value):
                raise ValueError(f"{name} must be nonnegative and finite")
        if self.theta is not None and not _finite(self.theta, signed=True):
            raise ValueError("Theta must be signed and finite")
        flags = (
            self.oi_unit_verified,
            self.oi_timestamp_verified,
            self.volume_unit_verified,
            self.volume_timestamp_verified,
            self.premium_unit_verified,
            self.oi_change_verified,
            self.iv_verified,
            self.greeks_verified,
            self.data_only,
            self.execution_authority,
            self.risk_authority,
            self.position_authority,
            self.certification_authority,
            self.live_execution_eligible,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Verification/authority flags must be exact booleans")
        if (self.oi_unit_verified or self.oi_timestamp_verified) and self.open_interest is None:
            raise ValueError("Verified OI value is missing")
        if (self.volume_unit_verified or self.volume_timestamp_verified) and self.volume is None:
            raise ValueError("Verified volume value is missing")
        for name in ("oi_unit", "volume_unit"):
            unit = getattr(self, name)
            if unit is not None and not _text(unit):
                raise ValueError(f"Invalid {name}")
        if self.oi_unit_verified and self.oi_unit in (None, "UNKNOWN", "UNVERIFIED"):
            raise ValueError("Verified OI requires a named unit")
        if self.volume_unit_verified and self.volume_unit in (None, "UNKNOWN", "UNVERIFIED"):
            raise ValueError("Verified volume requires a named unit")
        if self.premium_unit is not None and not _text(self.premium_unit):
            raise ValueError("Invalid option premium unit")
        if self.premium_unit_verified and (
            not _text(self.premium_unit)
            or all(price is None for price in (self.ltp, self.bid_price, self.ask_price))
        ):
            raise ValueError("Verified premium unit requires its unit and a price")
        if self.oi_change_baseline_id is not None and not _text(self.oi_change_baseline_id):
            raise ValueError("Invalid OI comparison provenance")
        if self.oi_change_verified and (
            self.change_in_open_interest is None
            or not self.oi_unit_verified
            or not self.oi_timestamp_verified
            or not _text(self.oi_change_baseline_id)
        ):
            raise ValueError("Verified OI change requires OI unit and baseline evidence")
        if self.iv_unit is not None and self.iv_unit not in {"PERCENT", "DECIMAL", "UNVERIFIED"}:
            raise ValueError("Unknown IV unit")
        if self.iv_verified and (
            self.implied_volatility is None or self.iv_unit not in {"PERCENT", "DECIMAL"}
        ):
            raise ValueError("Verified IV requires a declared and verified unit")
        if self.greeks_verified and all(
            getattr(self, key) is None for key in ("delta", "gamma", "theta", "vega")
        ):
            raise ValueError("Verified Greeks require a value")
        if (
            self.schema_version != "X5_OPTION_OBSERVATION_V1"
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Option observation authority must remain disabled")


@dataclass(frozen=True, slots=True)
class X5ChainCaptureV1:
    """Frozen capture with independent source time and retrieval time."""

    contract: X5ContractV1
    session_id: str
    capture_id: str
    source_id: str
    as_of: datetime
    captured_at: datetime
    observations: tuple[X5OptionObservationV1, ...]
    underlying_value: float | None = None
    underlying_unit: str | None = None
    underlying_verified: bool = False
    capture_verified: bool = False
    expiry_verified: bool = False
    timestamp_semantics_verified: bool = False
    historical_retrieval: bool = False
    point_in_time_verified: bool = False
    schema_version: str = "X5_OPTION_CAPTURE_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.contract, X5ContractV1):
            raise ValueError("A canonical five-market contract is required")
        if not all(_text(x) for x in (self.session_id, self.capture_id, self.source_id)):
            raise ValueError("Session, capture and source identity are required")
        if not _aware(self.as_of) or not _aware(self.captured_at):
            raise ValueError("As-of and retrieval timestamps must be timezone-aware")
        if type(self.observations) is not tuple or any(
            not isinstance(x, X5OptionObservationV1) for x in self.observations
        ):
            raise ValueError("Observations must form an immutable tuple")
        flags = (
            self.underlying_verified,
            self.capture_verified,
            self.expiry_verified,
            self.timestamp_semantics_verified,
            self.historical_retrieval,
            self.point_in_time_verified,
            self.data_only,
            self.execution_authority,
            self.risk_authority,
            self.position_authority,
            self.certification_authority,
            self.live_execution_eligible,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Capture flags must be exact booleans")
        if self.underlying_value is not None and not _finite(self.underlying_value, positive=True):
            raise ValueError("Underlying price must be positive and finite")
        required_underlying_unit = {
            "NIFTY": "INDEX_POINTS",
            "SENSEX": "INDEX_POINTS",
            "CRUDEOILM": "INR_PER_BARREL",
            "GOLDM": "INR_PER_10G",
            "NATGASMINI": "INR_PER_MMBTU",
        }[self.contract.market]
        if self.underlying_unit is not None and not _text(self.underlying_unit):
            raise ValueError("Invalid underlying unit")
        if self.underlying_verified and (
            self.underlying_value is None
            or not _text(self.underlying_unit)
            or self.underlying_unit != required_underlying_unit
        ):
            raise ValueError("Underlying verification requires matching value and unit")
        if self.point_in_time_verified and (
            not self.capture_verified
            or not self.timestamp_semantics_verified
            or not self.expiry_verified
            or self.historical_retrieval
            or self.captured_at > self.as_of
        ):
            raise ValueError("Point-in-time verification requires contemporaneous provenance")
        if self.captured_at > self.as_of and not self.historical_retrieval:
            raise ValueError("Retrieval after as-of must be explicitly marked retrospective")
        if (
            self.schema_version != "X5_OPTION_CAPTURE_V1"
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Option capture authority must remain disabled")
        root = {
            "NIFTY": "NSE:NIFTY",
            "SENSEX": "BSE:SENSEX",
            "CRUDEOILM": "MCX:CRUDEOILM",
            "GOLDM": "MCX:GOLDM",
            "NATGASMINI": "MCX:NATGASMINI",
        }[self.contract.market]
        seen_ids: set[str] = set()
        seen_symbols: set[str] = set()
        seen_strikes: set[tuple[float, str]] = set()
        seen_source_ids: set[str] = set()
        for row in self.observations:
            if row.expiry != self.contract.expiry or not row.provider_symbol.startswith(root):
                raise ValueError("Mixed expiry, exchange or provider symbol")
            if row.observed_at > self.as_of or row.observed_at > self.captured_at:
                raise ValueError("Future-dated option observation")
            key = (float(row.strike), row.option_type)
            if (
                row.canonical_option_id in seen_ids
                or row.provider_symbol in seen_symbols
                or key in seen_strikes
                or row.source_record_id in seen_source_ids
            ):
                raise ValueError("Duplicate option identity, strike/side or source record")
            seen_ids.add(row.canonical_option_id)
            seen_symbols.add(row.provider_symbol)
            seen_strikes.add(key)
            seen_source_ids.add(row.source_record_id)
        # Normalize input order so the canonical hash is independent of row arrival order.
        object.__setattr__(
            self,
            "observations",
            tuple(sorted(self.observations, key=lambda row: (float(row.strike), row.option_type))),
        )

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class X5ChainValidationV1:
    """Research eligibility report, never an entry or option-selection decision."""

    market: str
    expiry: date
    capture_id: str
    as_of: datetime
    status: str
    call_count: int
    put_count: int
    complete_pair_count: int
    call_only_count: int
    put_only_count: int
    readiness: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_capture_sha256: str
    schema_version: str = "X5_OPTION_VALIDATION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKET_EXCHANGES or not _aware(self.as_of):
            raise ValueError("Invalid validation identity")
        if self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("Invalid validation status")
        if not all(
            type(x) is int and x >= 0
            for x in (
                self.call_count,
                self.put_count,
                self.complete_pair_count,
                self.call_only_count,
                self.put_only_count,
            )
        ):
            raise ValueError("Invalid validation counts")
        if self.complete_pair_count + self.call_only_count != self.call_count or (
            self.complete_pair_count + self.put_only_count != self.put_count
        ):
            raise ValueError("Inconsistent CE/PE pairing counts")
        if type(self.readiness) is not tuple or any(
            type(item) is not tuple
            or len(item) != 2
            or not _text(item[0])
            or item[1] not in {"AVAILABLE", "UNAVAILABLE"}
            for item in self.readiness
        ):
            raise ValueError("Invalid metric readiness")
        if len({name for name, _ in self.readiness}) != len(self.readiness):
            raise ValueError("Duplicate readiness metrics")
        if not _text(self.capture_id) or not _text(self.source_capture_sha256):
            raise ValueError("Capture identity and hash required")
        if (
            self.schema_version != "X5_OPTION_VALIDATION_V1"
            or self.data_only is not True
            or any(
                (
                    self.independent_vote,
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Research validation has no trading authority")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())
