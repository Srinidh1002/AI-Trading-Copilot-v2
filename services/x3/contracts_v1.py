"""Immutable, deterministic, zero-authority X3 feature/result contracts."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

MARKETS = frozenset({"NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"})
FAMILIES = (
    "TREND",
    "MOMENTUM",
    "EXHAUSTION",
    "VOLATILITY",
    "VOLUME_PARTICIPATION",
    "STRUCTURE",
    "PATTERN",
)
STATES = frozenset({"BULLISH", "BEARISH", "NON_DIRECTIONAL", "UNKNOWN", "CONFLICT", "MISSING"})
STATUSES = frozenset(
    {"VALID", "UNAVAILABLE", "INSUFFICIENT_HISTORY", "MALFORMED", "STALE", "UNVERIFIED"}
)


def _encoded(obj: Any) -> Any:
    if isinstance(obj, datetime):
        if obj.tzinfo is None or obj.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_encoded(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _encoded(v) for k, v in obj.items()}
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("non-finite result")
    return obj


def canonical_json(obj) -> str:
    return json.dumps(
        _encoded(asdict(obj)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class X3FeatureV1:
    feature_id: str
    market: str
    instrument_id: str
    timeframe: str
    family: str
    value: float | None
    unit: str
    direction: str
    status: str
    observed_at: datetime
    source_id: str
    required_history: int
    available_history: int
    dependency_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "X3_FEATURE_V1"
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    provider: str = "UNVERIFIED"

    def __post_init__(self):
        if (
            self.market not in MARKETS
            or self.family not in FAMILIES
            or self.direction not in STATES
            or self.status not in STATUSES
            or not self.feature_id
            or not self.instrument_id
            or not self.timeframe
            or not self.source_id
            or not self.unit
            or not self.provider
            or not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
            or not isinstance(self.required_history, int)
            or self.required_history < 1
            or not isinstance(self.available_history, int)
            or self.available_history < 0
            or (self.value is None) == (self.status == "VALID")
            or (
                self.value is not None
                and (
                    isinstance(self.value, bool)
                    or not isinstance(self.value, (float, int))
                    or not math.isfinite(self.value)
                )
            )
            or (self.status != "VALID" and not self.blockers)
        ):
            raise ValueError("Invalid X3 feature contract")
        for field in ("dependency_ids", "blockers", "warnings"):
            v = getattr(self, field)
            if not isinstance(v, tuple) or any(not isinstance(x, str) or not x for x in v):
                raise ValueError("Invalid X3 feature tuple")
        if (
            self.data_only is not True
            or self.execution_authority is not False
            or self.risk_authority is not False
            or self.position_authority is not False
            or self.certification_authority is not False
            or self.live_execution_eligible is not False
            or self.schema_version != "X3_FEATURE_V1"
        ):
            raise ValueError("X3 features have no trading authority")

    def to_dict(self):
        return json.loads(canonical_json(self))

    @property
    def sha256(self) -> str:
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class X3FamilyResultV1:
    family: str
    state: str
    member_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    shared_dependencies: tuple[str, ...] = ()
    schema_version: str = "X3_FAMILY_V1"

    def __post_init__(self):
        if (
            self.family not in FAMILIES
            or self.state not in STATES
            or len(set(self.member_ids)) != len(self.member_ids)
            or len(set(self.missing_ids)) != len(self.missing_ids)
            or set(self.member_ids) & set(self.missing_ids)
        ):
            raise ValueError("Invalid X3 family")

    def to_dict(self):
        return json.loads(canonical_json(self))


@dataclass(frozen=True, slots=True)
class X3TimeframeResultV1:
    market: str
    instrument_id: str
    timeframe: str
    as_of: datetime
    source_id: str
    features: tuple[X3FeatureV1, ...]
    families: tuple[X3FamilyResultV1, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "X3_TIMEFRAME_RESULT_V1"
    data_only: bool = True
    live_execution_eligible: bool = False

    def __post_init__(self):
        if (
            self.market not in MARKETS
            or not self.instrument_id
            or not self.timeframe
            or not self.source_id
            or not isinstance(self.as_of, datetime)
            or self.as_of.tzinfo is None
            or self.as_of.utcoffset() is None
            or len({x.feature_id for x in self.features}) != len(self.features)
            or len({x.family for x in self.families}) != len(self.families)
            or any(
                x.market != self.market
                or x.instrument_id != self.instrument_id
                or x.timeframe != self.timeframe
                or x.observed_at > self.as_of
                for x in self.features
            )
            or not self.data_only
            or self.live_execution_eligible
        ):
            raise ValueError("Invalid X3 timeframe result")

    def to_dict(self):
        return json.loads(canonical_json(self))

    @property
    def sha256(self):
        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class X3MultiTimeframeResultV1:
    market: str
    instrument_id: str
    as_of: datetime
    required_timeframes: tuple[str, ...]
    timeframe_results: tuple[X3TimeframeResultV1, ...]
    missing_timeframes: tuple[str, ...]
    alignment: str
    schema_version: str = "X3_MTF_RESULT_V1"
    data_only: bool = True
    live_execution_eligible: bool = False

    def __post_init__(self):
        names = tuple(x.timeframe for x in self.timeframe_results)
        if (
            self.market not in MARKETS
            or self.alignment not in STATES
            or not self.instrument_id
            or not self.required_timeframes
            or len(set(self.required_timeframes)) != len(self.required_timeframes)
            or names != tuple(t for t in self.required_timeframes if t in names)
            or self.missing_timeframes
            != tuple(t for t in self.required_timeframes if t not in names)
            or any(
                x.market != self.market
                or x.instrument_id != self.instrument_id
                or x.as_of != self.as_of
                for x in self.timeframe_results
            )
            or not self.data_only
            or self.live_execution_eligible
        ):
            raise ValueError("Invalid X3 MTF result")

    @property
    def sha256(self):
        return canonical_sha256(self)

    def to_dict(self):
        return json.loads(canonical_json(self))
