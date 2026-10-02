"""X8 five-market offline regime-evidence readiness; not a regime classifier.

References already-evaluated upstream outputs; supplied hashes/verification flags
are caller assertions, never independent authentication or trading authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import MARKETS, _aware, _sha, _text, canonical_sha256

FAMILIES = (
    "TECHNICAL",
    "BREADTH",
    "FUTURES",
    "OPTIONS",
    "VOLATILITY",
    "EXTERNAL_CONTEXT",
    "MARKET_SESSION",
    "DATA_QUALITY",
)
DEPENDENCY_GROUPS = {
    "TECHNICAL": "PRICE_TECHNICAL",
    "BREADTH": "BREADTH",
    "FUTURES": "DERIVATIVES_POSITIONING",
    "OPTIONS": "DERIVATIVES_POSITIONING",
    "VOLATILITY": "VOLATILITY",
    "EXTERNAL_CONTEXT": "EXTERNAL_CONTEXT",
    "MARKET_SESSION": "SESSION",
    "DATA_QUALITY": "DATA_QUALITY",
}
STATES = frozenset({"AVAILABLE", "PARTIAL", "UNVERIFIED", "STALE", "UNAVAILABLE"})
AUTHORITY_FIELDS = (
    "execution_authority",
    "risk_authority",
    "position_authority",
    "certification_authority",
    "live_execution_eligible",
)


def zero_authority(record: object, version: str) -> None:
    if (
        getattr(record, "schema_version") != version
        or getattr(record, "data_only") is not True
        or getattr(record, "independent_vote") is not False
        or any(getattr(record, name) is not False for name in AUTHORITY_FIELDS)
    ):
        raise ValueError("X8/X9/X10 schema and zero-authority fields are fixed")


def require_identity(market: str, session_id: str, capture_id: str, as_of: datetime) -> None:
    if (
        market not in MARKETS
        or not all(_text(value) for value in (session_id, capture_id))
        or not _aware(as_of)
    ):
        raise ValueError("Invalid five-market identity/session/capture/time")


@dataclass(frozen=True, slots=True)
class X8EvidenceReferenceV1:
    family: str
    source_id: str
    source_record_id: str
    source_sha256: str
    observed_at: datetime
    available_at: datetime | None
    state: str
    point_in_time_verified: bool
    schema_version: str = "X8_EVIDENCE_REFERENCE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.family not in FAMILIES
            or not all(_text(value) for value in (self.source_id, self.source_record_id))
            or not _sha(self.source_sha256)
            or not _aware(self.observed_at)
            or self.state not in STATES
            or type(self.point_in_time_verified) is not bool
        ):
            raise ValueError("Invalid source-bound regime reference")
        if self.available_at is not None and (
            not _aware(self.available_at) or self.available_at < self.observed_at
        ):
            raise ValueError("Availability must follow observation")
        if self.state == "AVAILABLE" and (
            self.available_at is None or not self.point_in_time_verified
        ):
            raise ValueError("AVAILABLE reference needs supplied point-in-time proof")
        zero_authority(self, "X8_EVIDENCE_REFERENCE_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X8RegimeReadinessV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    evidence: tuple[X8EvidenceReferenceV1, ...]
    required_families: tuple[str, ...]
    absent_required: tuple[str, ...]
    dependency_groups: tuple[tuple[str, tuple[str, ...]], ...]
    status: str
    regime_label: str = "UNASSESSED"
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "X8_REGIME_READINESS_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        require_identity(self.market, self.session_id, self.capture_id, self.as_of)
        if (
            type(self.evidence) is not tuple
            or any(type(row) is not X8EvidenceReferenceV1 for row in self.evidence)
            or tuple(row.family for row in self.evidence)
            != tuple(sorted((row.family for row in self.evidence), key=FAMILIES.index))
            or len({row.family for row in self.evidence}) != len(self.evidence)
        ):
            raise ValueError("X8 evidence must have unique canonical families")
        if (
            self.status not in {"READY", "PARTIAL", "UNAVAILABLE"}
            or self.regime_label != "UNASSESSED"
            or type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
        ):
            raise ValueError("X8 does not classify a trading regime")
        for row in self.evidence:
            if row.observed_at > self.as_of or (
                row.available_at is not None and row.available_at > self.as_of
            ):
                raise ValueError("Future evidence cannot enter an X8 capture")
        required = ("TECHNICAL", "MARKET_SESSION", "DATA_QUALITY") + (
            ("FUTURES",) if self.market not in ("NIFTY", "SENSEX") else ()
        )
        required = tuple(sorted(required, key=FAMILIES.index))
        by_family = {row.family: row for row in self.evidence}
        missing = tuple(name for name in required if name not in by_family)
        blockers = tuple(f"REQUIRED_{name}_MISSING" for name in missing) + tuple(
            f"REQUIRED_{name}_{by_family[name].state}"
            for name in required
            if name in by_family and by_family[name].state != "AVAILABLE"
        )
        warnings = tuple(
            f"OPTIONAL_{row.family}_{row.state}"
            for row in self.evidence
            if row.family not in required and row.state != "AVAILABLE"
        )
        grouped = {}
        for row in self.evidence:
            grouped.setdefault(DEPENDENCY_GROUPS[row.family], []).append(row.family)
        groups = tuple(
            (name, tuple(sorted(names, key=FAMILIES.index)))
            for name, names in sorted(grouped.items())
        )
        status = "UNAVAILABLE" if blockers else "PARTIAL" if warnings else "READY"
        if (
            self.required_families != required
            or self.absent_required != missing
            or self.blockers != blockers
            or self.warnings != warnings
            or self.dependency_groups != groups
            or self.status != status
            or len({(row.source_id, row.source_record_id) for row in self.evidence})
            != len(self.evidence)
        ):
            raise ValueError("X8 readiness cannot be upgraded or reconstructed inconsistently")
        zero_authority(self, "X8_REGIME_READINESS_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))
