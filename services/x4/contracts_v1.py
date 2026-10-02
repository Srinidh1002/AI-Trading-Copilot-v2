"""Versioned, immutable X4 futures research contracts. No provider or broker I/O."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256

MARKETS = frozenset({"NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"})
STATES = frozenset(
    {"LONG_BUILDUP", "SHORT_BUILDUP", "SHORT_COVERING", "LONG_UNWINDING", "FLAT", "UNKNOWN"}
)
FEATURE_STATUSES = frozenset({"AVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"})


def _aware(value: datetime) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _positive_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _nonnegative_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _encode(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def canonical_sha256(value: object) -> str:
    encoded = _encode(value)
    return sha256(
        json.dumps(encoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class X4ContractV1:
    market: str
    canonical_instrument_id: str
    provider: str
    provider_symbol: str
    expiry: date
    price_unit: str
    metadata_status: str
    metadata_source: str
    schema_version: str = "X4_FUTURES_CONTRACT_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKETS:
            raise ValueError("Unsupported X4 market")
        if not all(
            isinstance(v, str) and v.strip() == v and v
            for v in (
                self.canonical_instrument_id,
                self.provider,
                self.provider_symbol,
                self.price_unit,
                self.metadata_source,
            )
        ):
            raise ValueError("Contract identity, unit and metadata source are required")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("Contract expiry must be a date")
        if self.metadata_status not in {"VERIFIED", "PROVISIONAL", "UNAVAILABLE"}:
            raise ValueError("Unknown contract metadata status")
        if (
            self.schema_version != "X4_FUTURES_CONTRACT_V1"
            or not self.data_only
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
            raise ValueError("X4 authority and schema fields are immutable")


@dataclass(frozen=True, slots=True)
class X4SampleV1:
    contract_id: str
    session_id: str
    timeframe: str
    observed_at: datetime
    source_id: str
    close: float
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    volume_verified: bool = False
    oi_verified: bool = False
    is_closed: bool = False
    quality: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not all(
            isinstance(v, str) and v.strip() == v and v
            for v in (
                self.contract_id,
                self.session_id,
                self.timeframe,
                self.source_id,
            )
        ):
            raise ValueError("Sample identity is required")
        if not _aware(self.observed_at):
            raise ValueError("Sample timestamp must be timezone-aware")
        if not _positive_number(self.close):
            raise ValueError("Sample close must be positive and finite")
        if (self.high is None) != (self.low is None):
            raise ValueError("High and low must both be present or absent")
        if self.high is not None and (
            not _positive_number(self.low)
            or not _positive_number(self.high)
            or self.low > self.close
            or self.high < self.close
        ):
            raise ValueError("Invalid high/low/close")
        if self.volume is not None and not _nonnegative_number(self.volume):
            raise ValueError("Volume must be nonnegative and finite")
        if self.open_interest is not None and not _positive_number(self.open_interest):
            raise ValueError("OI must be positive and finite when present")
        if (
            type(self.volume_verified) is not bool
            or type(self.oi_verified) is not bool
            or type(self.is_closed) is not bool
        ):
            raise ValueError("Quality flags must be boolean")
        if self.volume_verified and self.volume is None:
            raise ValueError("Verified volume is absent")
        if self.oi_verified and self.open_interest is None:
            raise ValueError("Verified OI is absent")
        if self.quality not in {"VALID", "STALE", "INVALID", "UNKNOWN"}:
            raise ValueError("Unknown quality state")


@dataclass(frozen=True, slots=True)
class X4BasisReferenceV1:
    market: str
    benchmark_type: str
    price: float
    price_unit: str
    source_id: str
    observed_at: datetime
    verified: bool

    def __post_init__(self) -> None:
        if self.market not in MARKETS or self.benchmark_type not in {
            "INDEX_SPOT",
            "VERIFIED_COMMODITY_SPOT",
        }:
            raise ValueError("Unsupported basis benchmark")
        if not _positive_number(self.price) or not _aware(self.observed_at):
            raise ValueError("Invalid benchmark price or timestamp")
        if not self.price_unit or not self.source_id or type(self.verified) is not bool:
            raise ValueError("Invalid benchmark provenance")


@dataclass(frozen=True, slots=True)
class X4FeatureV1:
    feature_id: str
    status: str
    value: float | None
    unit: str
    direction: str
    dependency_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    schema_version: str = "X4_FEATURE_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not self.feature_id or not self.unit or self.status not in FEATURE_STATUSES:
            raise ValueError("Invalid feature identity, unit or status")
        if self.status == "AVAILABLE" and not _nonnegative_number(
            abs(self.value) if self.value is not None else None
        ):
            raise ValueError("Available feature must have finite numeric value")
        if self.status != "AVAILABLE" and self.value is not None:
            raise ValueError("Unavailable feature cannot carry a value")
        if self.direction not in {"UP", "DOWN", "FLAT", "NON_DIRECTIONAL", "UNKNOWN"}:
            raise ValueError("Invalid direction")
        if (
            self.schema_version != "X4_FEATURE_V1"
            or not self.data_only
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
            raise ValueError("X4 feature authority must remain disabled")


@dataclass(frozen=True, slots=True)
class X4ResultV1:
    market: str
    instrument_id: str
    session_id: str
    timeframe: str
    as_of: datetime
    features: tuple[X4FeatureV1, ...]
    positioning_state: str
    status: str
    blockers: tuple[str, ...]
    schema_version: str = "X4_FUTURES_RESULT_V1"
    data_only: bool = True
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not _aware(self.as_of)
            or self.positioning_state not in STATES
        ):
            raise ValueError("Invalid result identity, time or state")
        if self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("Invalid result status")
        if len({x.feature_id for x in self.features}) != len(self.features):
            raise ValueError("Duplicate X4 features")
        if (
            self.schema_version != "X4_FUTURES_RESULT_V1"
            or not self.data_only
            or self.live_execution_eligible
        ):
            raise ValueError("X4 result authority must remain disabled")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())
