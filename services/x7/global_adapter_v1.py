"""Offline provider-neutral global/India VIX adapter; verified claims only.

The upstream caller supplies *separate* source evidence. A parsed record or
matching proof is not independent validation of the external publisher.
No network access, direction, correlation score, voting or trade authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import (
    GLOBAL_TYPES,
    GLOBAL_UNITS,
    MARKETS,
    SESSION_REFERENCES,
    X7GlobalObservationV1,
    _authority,
    _aware,
    _number,
    _text,
    canonical_sha256,
)

_RAW_KEYS = frozenset(
    {
        "name",
        "observation_type",
        "unit",
        "session_reference",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
        "value",
        "previous_value",
    }
)
_GROUPS = {
    "GIFT_INDEX_FUTURE": ("GIFT_NIFTY",),
    "US_EQUITY_CLOSES": ("SP500", "NASDAQ", "DOW_JONES"),
    "ASIAN_EQUITY_CLOSES": ("NIKKEI_225", "HANG_SENG", "SHANGHAI_COMPOSITE"),
    "CRUDE_BENCHMARKS": ("BRENT_CRUDE", "WTI_CRUDE"),
    "FX_CONTEXT": ("DXY", "USD_INR"),
    "BOND_YIELDS": ("US_10Y_YIELD", "INDIA_10Y_YIELD"),
    "INDIA_VOLATILITY": ("INDIA_VIX",),
}


def _sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True, slots=True)
class X7GlobalSourceProofV1:
    """Caller-supplied attestation, never generated from the raw quote itself."""

    name: str
    source_id: str
    source_record_id: str
    observation_type: str
    unit: str
    session_reference: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    source_verified: bool
    timestamp_semantics_verified: bool
    value_unit_verified: bool
    value_verified: bool
    schema_version: str = "X7_GLOBAL_SOURCE_PROOF_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.name not in GLOBAL_TYPES
            or self.observation_type != GLOBAL_TYPES[self.name]
            or self.unit != GLOBAL_UNITS[self.name]
            or self.session_reference not in SESSION_REFERENCES
            or not _text(self.source_id)
            or not _text(self.source_record_id)
            or not _aware(self.observed_at)
        ):
            raise ValueError("Invalid exact global-source identity or timestamp")
        if self.published_at is not None and (
            not _aware(self.published_at) or self.published_at < self.observed_at
        ):
            raise ValueError("Publication time is missing or precedes observation")
        if self.available_at is not None and (
            not _aware(self.available_at)
            or self.published_at is None
            or self.available_at < self.published_at
        ):
            raise ValueError("Availability must follow a known publication")
        flags = (
            self.source_verified,
            self.timestamp_semantics_verified,
            self.value_unit_verified,
            self.value_verified,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Source-attestation flags must be exact booleans")
        if self.source_verified and (
            not self.timestamp_semantics_verified
            or self.published_at is None
            or self.available_at is None
        ):
            raise ValueError("Source verification requires verified timing semantics")
        if self.value_verified and (not self.source_verified or not self.value_unit_verified):
            raise ValueError("Verified value requires source and exact unit proof")
        _authority(self, "X7_GLOBAL_SOURCE_PROOF_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7GlobalAdaptedObservationV1:
    observation: X7GlobalObservationV1
    raw_record_sha256: str
    proof_sha256: str
    as_of: datetime
    max_age_seconds: float
    schema_version: str = "X7_GLOBAL_ADAPTED_OBSERVATION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.observation, X7GlobalObservationV1)
            or not _sha(self.raw_record_sha256)
            or not _sha(self.proof_sha256)
            or not _aware(self.as_of)
            or type(self.max_age_seconds) not in (int, float)
            or not math.isfinite(self.max_age_seconds)
            or self.max_age_seconds <= 0
        ):
            raise ValueError("Invalid adapted observation/provenance")
        if self.observation.observed_at > self.as_of:
            raise ValueError("Observed time cannot be future dated")
        _authority(self, "X7_GLOBAL_ADAPTED_OBSERVATION_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7GlobalBatchV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    observations: tuple[X7GlobalAdaptedObservationV1, ...]
    dependency_groups: tuple[tuple[str, tuple[str, ...]], ...]
    input_sha256: str
    schema_version: str = "X7_GLOBAL_BATCH_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not _text(self.session_id)
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or not _sha(self.input_sha256)
            or type(self.observations) is not tuple
            or any(not isinstance(row, X7GlobalAdaptedObservationV1) for row in self.observations)
            or any(row.as_of != self.as_of for row in self.observations)
        ):
            raise ValueError("Invalid five-market global batch")
        names = tuple(row.observation.name for row in self.observations)
        if len(names) != len(set(names)) or names != tuple(sorted(names)):
            raise ValueError("Global observations must be unique and name-sorted")
        expected_groups = _dependency_groups(names)
        if self.dependency_groups != expected_groups:
            raise ValueError("Only fixed, descriptive dependency groups are allowed")
        _authority(self, "X7_GLOBAL_BATCH_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def _dependency_groups(names: tuple[str, ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    found = set(names)
    return tuple(
        (group, tuple(name for name in members if name in found))
        for group, members in _GROUPS.items()
        if found.intersection(members)
    )


def adapt_x7_global_observation_v1(
    *,
    raw_record: Mapping[str, object],
    proof: X7GlobalSourceProofV1,
    as_of: datetime,
    max_age_seconds: float,
) -> X7GlobalAdaptedObservationV1:
    """Adapt one exact normalized record, with no source/units/timing inference."""
    if not isinstance(raw_record, Mapping) or set(raw_record) != _RAW_KEYS:
        raise ValueError("Normalized global record requires the exact supported fields")
    if not isinstance(proof, X7GlobalSourceProofV1) or not _aware(as_of):
        raise TypeError("Exact proof and timezone-aware as_of are required")
    if (
        type(max_age_seconds) not in (int, float)
        or not math.isfinite(max_age_seconds)
        or max_age_seconds <= 0
    ):
        raise ValueError("Explicit positive freshness budget is required")
    for field in (
        "name",
        "observation_type",
        "unit",
        "session_reference",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
    ):
        if raw_record[field] != getattr(proof, field):
            raise ValueError(f"Raw global record conflicts with independent {field} proof")
    if (
        proof.observed_at > as_of
        or (proof.published_at is not None and proof.published_at > as_of)
        or (proof.available_at is not None and proof.available_at > as_of)
    ):
        raise ValueError("Global record would introduce future/unavailable evidence")
    value = raw_record["value"]
    previous = raw_record["previous_value"]
    signed = proof.observation_type == "BOND_YIELD"
    for label, number in (("value", value), ("previous_value", previous)):
        if number is not None and not _number(number, positive=not signed, signed=signed):
            raise ValueError(f"{label} must have the exact finite canonical unit")
    if proof.value_verified and value is None:
        raise ValueError("Cannot verify an absent measurement")
    verified = proof.value_verified and proof.source_verified
    if value is None:
        status = "UNAVAILABLE"
    elif not verified:
        status = "UNVERIFIED"
    elif (as_of - proof.observed_at).total_seconds() > max_age_seconds:
        status = "STALE"
    else:
        status = "AVAILABLE"
    observation = X7GlobalObservationV1(
        name=proof.name,
        observation_type=proof.observation_type,
        unit=proof.unit,
        session_reference=proof.session_reference,
        source_id=proof.source_id,
        observed_at=proof.observed_at,
        published_at=proof.published_at,
        available_at=proof.available_at,
        source_verified=proof.source_verified,
        value=value,
        value_verified=bool(verified and value is not None),
        previous_value=previous,
        status=status,
        source_record_id=proof.source_record_id,
    )
    return X7GlobalAdaptedObservationV1(
        observation=observation,
        raw_record_sha256=canonical_sha256(dict(raw_record)),
        proof_sha256=proof.sha256(),
        as_of=as_of,
        max_age_seconds=max_age_seconds,
    )


def adapt_x7_global_batch_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    raw_records: tuple[Mapping[str, object], ...],
    proofs: tuple[X7GlobalSourceProofV1, ...],
    max_age_seconds_by_name: Mapping[str, float],
) -> X7GlobalBatchV1:
    """Group captured facts descriptively; never assign votes or directional scores."""
    if market not in MARKETS or not _text(session_id) or not _text(capture_id):
        raise ValueError("Exact five-market identity and session/capture IDs required")
    if not _aware(as_of) or type(raw_records) is not tuple or type(proofs) is not tuple:
        raise ValueError("Aware as_of and immutable ordered record/proof tuples required")
    if len(raw_records) != len(proofs) or not isinstance(max_age_seconds_by_name, Mapping):
        raise ValueError("Every source record requires a distinct matching proof and budget")
    names = tuple(proof.name for proof in proofs if isinstance(proof, X7GlobalSourceProofV1))
    if len(names) != len(proofs) or len(set(names)) != len(names):
        raise ValueError("Source proofs must be typed and have unique global names")
    if len({proof.source_record_id for proof in proofs}) != len(proofs):
        raise ValueError("Source-record identities cannot be repeated within one batch")
    if set(max_age_seconds_by_name) != set(names):
        raise ValueError("Freshness policy must identify exactly the supplied global names")
    rows = tuple(
        adapt_x7_global_observation_v1(
            raw_record=record,
            proof=proof,
            as_of=as_of,
            max_age_seconds=max_age_seconds_by_name[proof.name],
        )
        for record, proof in zip(raw_records, proofs, strict=True)
    )
    sorted_rows = tuple(sorted(rows, key=lambda row: row.observation.name))
    return X7GlobalBatchV1(
        market=market,
        session_id=session_id,
        capture_id=capture_id,
        as_of=as_of,
        observations=sorted_rows,
        dependency_groups=_dependency_groups(tuple(row.observation.name for row in sorted_rows)),
        input_sha256=canonical_sha256(
            {
                "records": [row.raw_record_sha256 for row in sorted_rows],
                "proofs": [row.proof_sha256 for row in sorted_rows],
                "budgets": {row.observation.name: row.max_age_seconds for row in sorted_rows},
            }
        ),
    )


__all__ = [
    "X7GlobalSourceProofV1",
    "X7GlobalAdaptedObservationV1",
    "X7GlobalBatchV1",
    "adapt_x7_global_observation_v1",
    "adapt_x7_global_batch_v1",
]
