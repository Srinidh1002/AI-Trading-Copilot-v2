"""X8-B2 freshness-aware regime *input diagnostics*, not a regime prediction.

Direction, volatility regime, and strategy suitability remain UNASSESSED until
verified X2/X3/X4/X6 result adapters and an independently reviewed policy exist.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from services.x7.contracts_v1 import _sha, canonical_sha256
from services.x8.contracts_v1 import (
    FAMILIES,
    X8RegimeReadinessV1,
    zero_authority,
)

_DIAGNOSTIC = frozenset({"USABLE", "STALE", "UNVERIFIED", "PARTIAL", "UNAVAILABLE"})


def _budget(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("Finite positive maximum observation age is required")
    return float(value)


def _calculate(source: X8RegimeReadinessV1, budget: float):
    rows = []
    for ref in source.evidence:
        age = (source.as_of - ref.observed_at).total_seconds()
        if age < 0:
            raise ValueError("Future observation is not admissible")
        if ref.state == "UNAVAILABLE":
            diagnostic = "UNAVAILABLE"
        elif (
            not ref.point_in_time_verified or ref.available_at is None or ref.state == "UNVERIFIED"
        ):
            diagnostic = "UNVERIFIED"
        elif ref.state == "STALE" or age > budget:
            diagnostic = "STALE"
        elif ref.state == "PARTIAL":
            diagnostic = "PARTIAL"
        else:
            diagnostic = "USABLE"
        rows.append((ref.family, ref.sha256(), age, diagnostic))
    by_family = {row[0]: row[3] for row in rows}
    missing = tuple(f for f in source.required_families if by_family.get(f) != "USABLE")
    usable = sum(row[3] == "USABLE" for row in rows)
    state = (
        "UNAVAILABLE"
        if missing
        else "PARTIAL"
        if usable != len(rows)
        else "READY_FOR_CLASSIFICATION"
    )
    return tuple(rows), missing, state


@dataclass(frozen=True, slots=True)
class X8RegimeDescriptionV1:
    market: str
    session_id: str
    capture_id: str
    as_of: object
    x8_readiness_sha256: str
    maximum_observation_age_seconds: float
    family_diagnostics: tuple[tuple[str, str, float, str], ...]
    unusable_required_families: tuple[str, ...]
    research_status: str
    regime_label: str = "UNASSESSED"
    direction: str = "UNASSESSED"
    volatility_regime: str = "UNASSESSED"
    schema_version: str = "X8_REGIME_DESCRIPTION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        from services.x7.contracts_v1 import MARKETS, _aware, _text

        if (
            self.market not in MARKETS
            or not _text(self.session_id)
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or not _sha(self.x8_readiness_sha256)
            or self.research_status not in {"UNAVAILABLE", "PARTIAL", "READY_FOR_CLASSIFICATION"}
            or any(
                x != "UNASSESSED"
                for x in (self.regime_label, self.direction, self.volatility_regime)
            )
            or type(self.family_diagnostics) is not tuple
            or type(self.unusable_required_families) is not tuple
        ):
            raise ValueError("Invalid zero-authority X8 descriptive result")
        _budget(self.maximum_observation_age_seconds)
        families = tuple(row[0] for row in self.family_diagnostics)
        if (
            any(type(row) is not tuple or len(row) != 4 for row in self.family_diagnostics)
            or families != tuple(sorted(families, key=FAMILIES.index))
            or len(set(families)) != len(families)
        ):
            raise ValueError("Noncanonical or duplicate X8 family diagnostics")
        for family, digest, age, state in self.family_diagnostics:
            if (
                family not in FAMILIES
                or not _sha(digest)
                or type(age) is not float
                or not math.isfinite(age)
                or age < 0
                or state not in _DIAGNOSTIC
            ):
                raise ValueError("Invalid source-bound diagnostic")
        required = ("TECHNICAL", "MARKET_SESSION", "DATA_QUALITY") + (
            ("FUTURES",) if self.market not in ("NIFTY", "SENSEX") else ()
        )
        required = tuple(sorted(required, key=FAMILIES.index))
        states = {family: state for family, _, _, state in self.family_diagnostics}
        missing = tuple(f for f in required if states.get(f) != "USABLE")
        derived_status = (
            "UNAVAILABLE"
            if missing
            else "PARTIAL"
            if any(state != "USABLE" for state in states.values())
            else "READY_FOR_CLASSIFICATION"
        )
        if self.unusable_required_families != missing or self.research_status != derived_status:
            raise ValueError("X8 descriptor cannot upgrade incomplete evidence")
        zero_authority(self, "X8_REGIME_DESCRIPTION_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def describe_x8_regime_evidence_v1(
    *, readiness: X8RegimeReadinessV1, max_age_seconds: float
) -> X8RegimeDescriptionV1:
    if type(readiness) is not X8RegimeReadinessV1:
        raise TypeError("Original immutable X8 readiness is required")
    budget = _budget(max_age_seconds)
    rows, missing, status = _calculate(readiness, budget)
    return X8RegimeDescriptionV1(
        readiness.market,
        readiness.session_id,
        readiness.capture_id,
        readiness.as_of,
        readiness.sha256(),
        budget,
        rows,
        missing,
        status,
    )


def validate_x8_regime_description_v1(
    *, readiness: X8RegimeReadinessV1, description: X8RegimeDescriptionV1
) -> None:
    if type(description) is not X8RegimeDescriptionV1:
        raise TypeError("Exact immutable X8 description required")
    expected = describe_x8_regime_evidence_v1(
        readiness=readiness,
        max_age_seconds=description.maximum_observation_age_seconds,
    )
    if expected != description:
        raise ValueError("X8 description does not match original source readiness")
