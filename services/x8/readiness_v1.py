"""Pure readiness diagnostics; no indicator recomputation, score or action."""

from __future__ import annotations

from datetime import datetime

from services.x8.contracts_v1 import (
    DEPENDENCY_GROUPS,
    FAMILIES,
    X8EvidenceReferenceV1,
    X8RegimeReadinessV1,
    require_identity,
)


def build_x8_regime_readiness_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    evidence: tuple[X8EvidenceReferenceV1, ...],
) -> X8RegimeReadinessV1:
    require_identity(market, session_id, capture_id, as_of)
    if type(evidence) is not tuple or any(
        type(row) is not X8EvidenceReferenceV1 for row in evidence
    ):
        raise TypeError("X8 requires supplied immutable evidence references")
    by_family = {row.family: row for row in evidence}
    if len(by_family) != len(evidence):
        raise ValueError("Duplicate upstream evidence family")
    if len({(row.source_id, row.source_record_id) for row in evidence}) != len(evidence):
        raise ValueError("Same source record cannot masquerade as two independent facts")
    for row in evidence:
        if row.observed_at > as_of or (row.available_at is not None and row.available_at > as_of):
            raise ValueError("Evidence was not available at the capture time")
    required = ("TECHNICAL", "MARKET_SESSION", "DATA_QUALITY") + (
        ("FUTURES",) if market not in ("NIFTY", "SENSEX") else ()
    )
    required = tuple(sorted(required, key=FAMILIES.index))
    absent = tuple(name for name in required if name not in by_family)
    invalid = tuple(
        name for name in required if name in by_family and by_family[name].state != "AVAILABLE"
    )
    blockers = tuple(f"REQUIRED_{name}_MISSING" for name in absent) + tuple(
        f"REQUIRED_{name}_{by_family[name].state}" for name in invalid
    )
    warnings = tuple(
        f"OPTIONAL_{row.family}_{row.state}"
        for row in evidence
        if row.family not in required and row.state != "AVAILABLE"
    )
    status = "UNAVAILABLE" if blockers else "PARTIAL" if warnings else "READY"
    grouped = {}
    for row in evidence:
        grouped.setdefault(DEPENDENCY_GROUPS[row.family], []).append(row.family)
    groups = tuple(
        (name, tuple(sorted(names, key=FAMILIES.index))) for name, names in sorted(grouped.items())
    )
    return X8RegimeReadinessV1(
        market,
        session_id,
        capture_id,
        as_of,
        tuple(sorted(evidence, key=lambda row: FAMILIES.index(row.family))),
        required,
        absent,
        groups,
        status,
        "UNASSESSED",
        blockers,
        warnings,
    )
