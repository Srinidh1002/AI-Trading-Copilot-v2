"""Deterministic evidence-eligibility policy for Shadow Brain V1.

This module does not aggregate a market hypothesis.

It only classifies frozen EvidenceV1 inputs into deterministic
policy states using the standardized status, freshness and
direction fields already produced by the B2 adapters.

Raw feature values are intentionally not interpreted here.
"""

from __future__ import annotations

from services.contracts.brain_evidence_v1 import (
    ANALYZER_STATUSES,
    EVIDENCE_DIRECTIONS,
    EVIDENCE_STATUSES,
    FRESHNESS_STATUSES,
    AnalyzerResultV1,
    EvidenceV1,
)


SHADOW_EVIDENCE_POLICY_SCHEMA_V1 = (
    "BRAIN_SHADOW_EVIDENCE_POLICY_V1"
)

SHADOW_EVIDENCE_POLICY_STATES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NON_DIRECTIONAL",
        "UNKNOWN",
    }
)

DIRECTIONAL_EVIDENCE_DIRECTIONS = frozenset(
    {
        "BULLISH",
        "BEARISH",
    }
)

NON_DIRECTIONAL_EVIDENCE_DIRECTIONS = frozenset(
    {
        "NEUTRAL",
        "MIXED",
    }
)

UNKNOWN_EVIDENCE_DIRECTIONS = frozenset(
    {
        "UNKNOWN",
    }
)

DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES = frozenset(
    {
        "AVAILABLE",
    }
)

NON_DIRECTIONAL_EVIDENCE_STATUSES = frozenset(
    EVIDENCE_STATUSES
    - DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES
)

DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES = frozenset(
    {
        "FRESH",
    }
)

NON_DIRECTIONAL_FRESHNESS_STATUSES = frozenset(
    FRESHNESS_STATUSES
    - DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES
)

EVALUABLE_ANALYZER_STATUSES = frozenset(
    {
        "OK",
        "PARTIAL",
    }
)

NON_EVALUABLE_ANALYZER_STATUSES = frozenset(
    ANALYZER_STATUSES
    - EVALUABLE_ANALYZER_STATUSES
)


def _validate_policy_partition() -> None:
    if (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        | NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
        | UNKNOWN_EVIDENCE_DIRECTIONS
    ) != EVIDENCE_DIRECTIONS:
        raise RuntimeError(
            "Shadow direction policy does not exactly partition "
            "the frozen EvidenceV1 direction vocabulary."
        )

    if (
        DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES
        | NON_DIRECTIONAL_EVIDENCE_STATUSES
    ) != EVIDENCE_STATUSES:
        raise RuntimeError(
            "Shadow status policy does not exactly partition "
            "the frozen EvidenceV1 status vocabulary."
        )

    if (
        DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES
        | NON_DIRECTIONAL_FRESHNESS_STATUSES
    ) != FRESHNESS_STATUSES:
        raise RuntimeError(
            "Shadow freshness policy does not exactly partition "
            "the frozen EvidenceV1 freshness vocabulary."
        )

    if (
        EVALUABLE_ANALYZER_STATUSES
        | NON_EVALUABLE_ANALYZER_STATUSES
    ) != ANALYZER_STATUSES:
        raise RuntimeError(
            "Shadow analyzer policy does not exactly partition "
            "the frozen AnalyzerResultV1 status vocabulary."
        )

    if (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        & NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
    ):
        raise RuntimeError(
            "Directional and non-directional policy sets overlap."
        )

    if (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        & UNKNOWN_EVIDENCE_DIRECTIONS
    ):
        raise RuntimeError(
            "Directional and unknown policy sets overlap."
        )

    if (
        NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
        & UNKNOWN_EVIDENCE_DIRECTIONS
    ):
        raise RuntimeError(
            "Non-directional and unknown policy sets overlap."
        )


_validate_policy_partition()


def classify_evidence_v1(
    evidence: EvidenceV1,
) -> str:
    """Classify one EvidenceV1 without interpreting raw feature values."""

    if not isinstance(
        evidence,
        EvidenceV1,
    ):
        raise TypeError(
            "evidence must be EvidenceV1."
        )

    if evidence.status not in (
        DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES
    ):
        return "UNKNOWN"

    if evidence.freshness not in (
        DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES
    ):
        return "UNKNOWN"

    if evidence.direction in DIRECTIONAL_EVIDENCE_DIRECTIONS:
        return evidence.direction

    if evidence.direction in NON_DIRECTIONAL_EVIDENCE_DIRECTIONS:
        return "NON_DIRECTIONAL"

    return "UNKNOWN"


def classify_analyzer_result_v1(
    result: AnalyzerResultV1,
) -> tuple[tuple[str, str], ...]:
    """Return deterministic evidence-ID/policy-state pairs."""

    if not isinstance(
        result,
        AnalyzerResultV1,
    ):
        raise TypeError(
            "result must be AnalyzerResultV1."
        )

    if result.status not in EVALUABLE_ANALYZER_STATUSES:
        return tuple(
            sorted(
                (
                    evidence.evidence_id,
                    "UNKNOWN",
                )
                for evidence in result.evidence
            )
        )

    return tuple(
        sorted(
            (
                evidence.evidence_id,
                classify_evidence_v1(evidence),
            )
            for evidence in result.evidence
        )
    )


def directional_evidence_ids_v1(
    result: AnalyzerResultV1,
    direction: str,
) -> tuple[str, ...]:
    """Return sorted evidence IDs eligible for one directional side."""

    if direction not in DIRECTIONAL_EVIDENCE_DIRECTIONS:
        raise ValueError(
            "direction must be BULLISH or BEARISH."
        )

    return tuple(
        evidence_id
        for evidence_id, state in classify_analyzer_result_v1(result)
        if state == direction
    )


def unknown_evidence_ids_v1(
    result: AnalyzerResultV1,
) -> tuple[str, ...]:
    """Return evidence that cannot participate in directional evaluation."""

    return tuple(
        evidence_id
        for evidence_id, state in classify_analyzer_result_v1(result)
        if state == "UNKNOWN"
    )


def non_directional_evidence_ids_v1(
    result: AnalyzerResultV1,
) -> tuple[str, ...]:
    """Return valid fresh evidence that is neutral or mixed."""

    return tuple(
        evidence_id
        for evidence_id, state in classify_analyzer_result_v1(result)
        if state == "NON_DIRECTIONAL"
    )


__all__ = [
    "SHADOW_EVIDENCE_POLICY_SCHEMA_V1",
    "SHADOW_EVIDENCE_POLICY_STATES",
    "DIRECTIONAL_EVIDENCE_DIRECTIONS",
    "NON_DIRECTIONAL_EVIDENCE_DIRECTIONS",
    "UNKNOWN_EVIDENCE_DIRECTIONS",
    "DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES",
    "NON_DIRECTIONAL_EVIDENCE_STATUSES",
    "DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES",
    "NON_DIRECTIONAL_FRESHNESS_STATUSES",
    "EVALUABLE_ANALYZER_STATUSES",
    "NON_EVALUABLE_ANALYZER_STATUSES",
    "classify_evidence_v1",
    "classify_analyzer_result_v1",
    "directional_evidence_ids_v1",
    "unknown_evidence_ids_v1",
    "non_directional_evidence_ids_v1",
]
