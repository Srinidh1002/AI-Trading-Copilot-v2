from __future__ import annotations

import ast
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import pytest

from services.contracts.brain_evidence_v1 import (
    ANALYZER_STATUSES,
    EVIDENCE_DIRECTIONS,
    EVIDENCE_STATUSES,
    FRESHNESS_STATUSES,
    AnalyzerResultV1,
    EvidenceV1,
)
from services.brain.shadow_evaluator_policy_v1 import (
    DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES,
    DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES,
    DIRECTIONAL_EVIDENCE_DIRECTIONS,
    EVALUABLE_ANALYZER_STATUSES,
    NON_DIRECTIONAL_EVIDENCE_DIRECTIONS,
    NON_DIRECTIONAL_EVIDENCE_STATUSES,
    NON_DIRECTIONAL_FRESHNESS_STATUSES,
    NON_EVALUABLE_ANALYZER_STATUSES,
    SHADOW_EVIDENCE_POLICY_STATES,
    UNKNOWN_EVIDENCE_DIRECTIONS,
    classify_analyzer_result_v1,
    classify_evidence_v1,
    directional_evidence_ids_v1,
    non_directional_evidence_ids_v1,
    unknown_evidence_ids_v1,
)


NOW = datetime(
    2026,
    9,
    30,
    10,
    0,
    tzinfo=timezone.utc,
)


def _raw_evidence(
    *,
    evidence_id: str = "e1",
    status: str = "AVAILABLE",
    freshness: str = "FRESH",
    direction: str = "BULLISH",
    feature: str = "TEST_FEATURE",
    value: object = 1.0,
    source_authoritative: bool = True,
    metadata: object = (),
) -> EvidenceV1:
    """
    Construct an isolated policy fixture without invoking EvidenceV1 validation.

    B4 policy tests intentionally exercise only the frozen standardized
    status/freshness/direction surface and do not duplicate B2 contract tests.
    """
    evidence = object.__new__(
        EvidenceV1
    )

    values = {
        "evidence_id": evidence_id,
        "market": "NIFTY",
        "analyzer": "index.mtf.legacy_v1",
        "analyzer_version": "1.0",
        "category": "TECHNICAL",
        "feature": feature,
        "observed_at": NOW,
        "generated_at": NOW,
        "status": status,
        "freshness": freshness,
        "source": "POLICY_TEST",
        "value": value,
        "unit": "TEST",
        "direction": direction,
        "strength": 0.5,
        "confidence": 0.5,
        "quality_score": 1.0,
        "source_authoritative": source_authoritative,
        "missing_reason": None,
        "blockers": (),
        "warnings": (),
        "metadata": metadata,
        "schema_version": "POLICY_TEST_FIXTURE",
    }

    for name, field_value in values.items():
        object.__setattr__(
            evidence,
            name,
            field_value,
        )

    return evidence


def _raw_result(
    *,
    status: str = "OK",
    evidence: tuple[EvidenceV1, ...] = (),
) -> AnalyzerResultV1:
    """
    Construct an isolated AnalyzerResultV1 policy fixture.

    AnalyzerResultV1 validation itself remains covered by the frozen B2 suite.
    """
    result = object.__new__(
        AnalyzerResultV1
    )

    values = {
        "result_id": "policy-result",
        "market": "NIFTY",
        "analyzer": "index.mtf.legacy_v1",
        "analyzer_version": "1.0",
        "generated_at": NOW,
        "status": status,
        "evidence": evidence,
        "blockers": (),
        "warnings": (),
        "execution_authority": False,
        "schema_version": "POLICY_TEST_FIXTURE",
    }

    for name, field_value in values.items():
        object.__setattr__(
            result,
            name,
            field_value,
        )

    return result


def _expected_state(
    status: str,
    freshness: str,
    direction: str,
) -> str:
    if status != "AVAILABLE":
        return "UNKNOWN"

    if freshness != "FRESH":
        return "UNKNOWN"

    if direction in {
        "BULLISH",
        "BEARISH",
    }:
        return direction

    if direction in {
        "NEUTRAL",
        "MIXED",
    }:
        return "NON_DIRECTIONAL"

    return "UNKNOWN"


FULL_EVIDENCE_MATRIX = list(
    product(
        sorted(EVIDENCE_STATUSES),
        sorted(FRESHNESS_STATUSES),
        sorted(EVIDENCE_DIRECTIONS),
    )
)


def test_policy_state_vocabulary_is_exact():
    assert SHADOW_EVIDENCE_POLICY_STATES == frozenset(
        {
            "BULLISH",
            "BEARISH",
            "NON_DIRECTIONAL",
            "UNKNOWN",
        }
    )


def test_direction_partition_matches_frozen_contract_exactly():
    assert (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        | NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
        | UNKNOWN_EVIDENCE_DIRECTIONS
    ) == EVIDENCE_DIRECTIONS

    assert (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        & NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
    ) == frozenset()

    assert (
        DIRECTIONAL_EVIDENCE_DIRECTIONS
        & UNKNOWN_EVIDENCE_DIRECTIONS
    ) == frozenset()

    assert (
        NON_DIRECTIONAL_EVIDENCE_DIRECTIONS
        & UNKNOWN_EVIDENCE_DIRECTIONS
    ) == frozenset()


def test_status_partition_matches_frozen_contract_exactly():
    assert (
        DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES
        | NON_DIRECTIONAL_EVIDENCE_STATUSES
    ) == EVIDENCE_STATUSES

    assert (
        DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES
        & NON_DIRECTIONAL_EVIDENCE_STATUSES
    ) == frozenset()

    assert DIRECTIONALLY_ELIGIBLE_EVIDENCE_STATUSES == frozenset(
        {
            "AVAILABLE",
        }
    )


def test_freshness_partition_matches_frozen_contract_exactly():
    assert (
        DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES
        | NON_DIRECTIONAL_FRESHNESS_STATUSES
    ) == FRESHNESS_STATUSES

    assert (
        DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES
        & NON_DIRECTIONAL_FRESHNESS_STATUSES
    ) == frozenset()

    assert DIRECTIONALLY_ELIGIBLE_FRESHNESS_STATUSES == frozenset(
        {
            "FRESH",
        }
    )


def test_analyzer_status_partition_matches_frozen_contract_exactly():
    assert (
        EVALUABLE_ANALYZER_STATUSES
        | NON_EVALUABLE_ANALYZER_STATUSES
    ) == ANALYZER_STATUSES

    assert (
        EVALUABLE_ANALYZER_STATUSES
        & NON_EVALUABLE_ANALYZER_STATUSES
    ) == frozenset()

    assert EVALUABLE_ANALYZER_STATUSES == frozenset(
        {
            "OK",
            "PARTIAL",
        }
    )


@pytest.mark.parametrize(
    "status,freshness,direction",
    FULL_EVIDENCE_MATRIX,
)
def test_full_status_freshness_direction_matrix(
    status,
    freshness,
    direction,
):
    evidence = _raw_evidence(
        status=status,
        freshness=freshness,
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == _expected_state(
        status,
        freshness,
        direction,
    )


def test_full_evidence_matrix_has_expected_size():
    assert len(
        FULL_EVIDENCE_MATRIX
    ) == (
        len(EVIDENCE_STATUSES)
        * len(FRESHNESS_STATUSES)
        * len(EVIDENCE_DIRECTIONS)
    )

    assert len(
        FULL_EVIDENCE_MATRIX
    ) == 80


@pytest.mark.parametrize(
    "direction",
    (
        "BULLISH",
        "BEARISH",
    ),
)
def test_fresh_available_directional_evidence_votes(
    direction,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness="FRESH",
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == direction


@pytest.mark.parametrize(
    "direction",
    tuple(
        sorted(
            EVIDENCE_DIRECTIONS
        )
    ),
)
def test_not_applicable_freshness_is_fail_closed(
    direction,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness="NOT_APPLICABLE",
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == "UNKNOWN"


@pytest.mark.parametrize(
    "freshness",
    (
        "STALE",
        "UNKNOWN",
    ),
)
@pytest.mark.parametrize(
    "direction",
    (
        "BULLISH",
        "BEARISH",
    ),
)
def test_noneligible_freshness_cannot_vote_directionally(
    freshness,
    direction,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness=freshness,
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == "UNKNOWN"


@pytest.mark.parametrize(
    "status",
    (
        "DEGRADED",
        "UNVERIFIED",
        "UNAVAILABLE",
    ),
)
@pytest.mark.parametrize(
    "direction",
    (
        "BULLISH",
        "BEARISH",
    ),
)
def test_nonavailable_status_cannot_vote_directionally(
    status,
    direction,
):
    evidence = _raw_evidence(
        status=status,
        freshness="FRESH",
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == "UNKNOWN"


@pytest.mark.parametrize(
    "direction",
    (
        "NEUTRAL",
        "MIXED",
    ),
)
def test_valid_fresh_neutral_and_mixed_are_non_directional(
    direction,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness="FRESH",
        direction=direction,
    )

    assert classify_evidence_v1(
        evidence
    ) == "NON_DIRECTIONAL"


@pytest.mark.parametrize(
    "freshness",
    (
        "FRESH",
        "NOT_APPLICABLE",
        "STALE",
        "UNKNOWN",
    ),
)
def test_unknown_direction_is_always_unknown(
    freshness,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness=freshness,
        direction="UNKNOWN",
    )

    assert classify_evidence_v1(
        evidence
    ) == "UNKNOWN"


@pytest.mark.parametrize(
    "result_status,expected_state",
    (
        ("OK", "BULLISH"),
        ("PARTIAL", "BULLISH"),
        ("ERROR", "UNKNOWN"),
        ("UNAVAILABLE", "UNKNOWN"),
    ),
)
def test_analyzer_status_gates_evidence_evaluation(
    result_status,
    expected_state,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness="FRESH",
        direction="BULLISH",
    )

    result = _raw_result(
        status=result_status,
        evidence=(
            evidence,
        ),
    )

    assert classify_analyzer_result_v1(
        result
    ) == (
        (
            "e1",
            expected_state,
        ),
    )


def test_partial_analyzer_preserves_per_evidence_policy():
    result = _raw_result(
        status="PARTIAL",
        evidence=(
            _raw_evidence(
                evidence_id="bull",
                direction="BULLISH",
            ),
            _raw_evidence(
                evidence_id="bear",
                direction="BEARISH",
            ),
            _raw_evidence(
                evidence_id="neutral",
                direction="NEUTRAL",
            ),
            _raw_evidence(
                evidence_id="unknown",
                status="UNVERIFIED",
                direction="BULLISH",
            ),
        ),
    )

    assert classify_analyzer_result_v1(
        result
    ) == (
        (
            "bear",
            "BEARISH",
        ),
        (
            "bull",
            "BULLISH",
        ),
        (
            "neutral",
            "NON_DIRECTIONAL",
        ),
        (
            "unknown",
            "UNKNOWN",
        ),
    )


def test_non_evaluable_analyzer_forces_all_evidence_unknown():
    result = _raw_result(
        status="ERROR",
        evidence=(
            _raw_evidence(
                evidence_id="bull",
                direction="BULLISH",
            ),
            _raw_evidence(
                evidence_id="bear",
                direction="BEARISH",
            ),
            _raw_evidence(
                evidence_id="neutral",
                direction="NEUTRAL",
            ),
        ),
    )

    assert classify_analyzer_result_v1(
        result
    ) == (
        (
            "bear",
            "UNKNOWN",
        ),
        (
            "bull",
            "UNKNOWN",
        ),
        (
            "neutral",
            "UNKNOWN",
        ),
    )


def test_analyzer_result_output_is_sorted_by_evidence_id():
    result = _raw_result(
        status="OK",
        evidence=(
            _raw_evidence(
                evidence_id="z-last",
                direction="BEARISH",
            ),
            _raw_evidence(
                evidence_id="a-first",
                direction="BULLISH",
            ),
            _raw_evidence(
                evidence_id="m-middle",
                direction="NEUTRAL",
            ),
        ),
    )

    assert classify_analyzer_result_v1(
        result
    ) == (
        (
            "a-first",
            "BULLISH",
        ),
        (
            "m-middle",
            "NON_DIRECTIONAL",
        ),
        (
            "z-last",
            "BEARISH",
        ),
    )


def test_directional_unknown_and_non_directional_helpers():
    result = _raw_result(
        status="OK",
        evidence=(
            _raw_evidence(
                evidence_id="b1",
                direction="BEARISH",
            ),
            _raw_evidence(
                evidence_id="b2",
                direction="BEARISH",
            ),
            _raw_evidence(
                evidence_id="n1",
                direction="NEUTRAL",
            ),
            _raw_evidence(
                evidence_id="u1",
                status="UNVERIFIED",
                direction="BULLISH",
            ),
            _raw_evidence(
                evidence_id="x1",
                direction="BULLISH",
            ),
        ),
    )

    assert directional_evidence_ids_v1(
        result,
        "BULLISH",
    ) == (
        "x1",
    )

    assert directional_evidence_ids_v1(
        result,
        "BEARISH",
    ) == (
        "b1",
        "b2",
    )

    assert non_directional_evidence_ids_v1(
        result
    ) == (
        "n1",
    )

    assert unknown_evidence_ids_v1(
        result
    ) == (
        "u1",
    )


@pytest.mark.parametrize(
    "direction",
    (
        "NEUTRAL",
        "MIXED",
        "UNKNOWN",
        "BUY_CALL",
        "",
    ),
)
def test_directional_helper_rejects_non_directional_request(
    direction,
):
    result = _raw_result()

    with pytest.raises(
        ValueError,
        match="direction must be BULLISH or BEARISH",
    ):
        directional_evidence_ids_v1(
            result,
            direction,
        )


def test_classify_evidence_rejects_wrong_type():
    with pytest.raises(
        TypeError,
        match="evidence must be EvidenceV1",
    ):
        classify_evidence_v1(
            object()
        )


def test_classify_result_rejects_wrong_type():
    with pytest.raises(
        TypeError,
        match="result must be AnalyzerResultV1",
    ):
        classify_analyzer_result_v1(
            object()
        )


def test_equal_raw_index_and_mcx_pcr_follow_source_direction():
    index_pcr = _raw_evidence(
        evidence_id="index-pcr",
        feature="PCR",
        value=0.30,
        direction="BULLISH",
        metadata=(
            (
                "source_interpretation",
                "INDEX_LEGACY_SOURCE_RULE",
            ),
        ),
    )

    mcx_pcr = _raw_evidence(
        evidence_id="mcx-pcr",
        feature="STABLE_PCR",
        value=0.30,
        direction="BEARISH",
        metadata=(
            (
                "source_interpretation",
                "MCX_NATIVE_LOW_PCR_BEARISH",
            ),
        ),
    )

    assert classify_evidence_v1(
        index_pcr
    ) == "BULLISH"

    assert classify_evidence_v1(
        mcx_pcr
    ) == "BEARISH"


@pytest.mark.parametrize(
    "feature,value",
    (
        ("PCR", 0.01),
        ("PCR", 0.30),
        ("PCR", 1.50),
        ("STABLE_PCR", 0.01),
        ("STABLE_PCR", 0.30),
        ("STABLE_PCR", 1.50),
        ("UNRELATED_FEATURE", -999.0),
        ("UNRELATED_FEATURE", 999.0),
    ),
)
def test_raw_feature_and_value_cannot_override_bullish_direction(
    feature,
    value,
):
    evidence = _raw_evidence(
        feature=feature,
        value=value,
        direction="BULLISH",
    )

    assert classify_evidence_v1(
        evidence
    ) == "BULLISH"


@pytest.mark.parametrize(
    "feature,value",
    (
        ("PCR", 0.01),
        ("PCR", 0.30),
        ("PCR", 1.50),
        ("STABLE_PCR", 0.01),
        ("STABLE_PCR", 0.30),
        ("STABLE_PCR", 1.50),
        ("UNRELATED_FEATURE", -999.0),
        ("UNRELATED_FEATURE", 999.0),
    ),
)
def test_raw_feature_and_value_cannot_override_bearish_direction(
    feature,
    value,
):
    evidence = _raw_evidence(
        feature=feature,
        value=value,
        direction="BEARISH",
    )

    assert classify_evidence_v1(
        evidence
    ) == "BEARISH"


def test_same_direction_same_policy_despite_different_raw_pcr_semantics():
    index = _raw_evidence(
        evidence_id="index",
        feature="PCR",
        value=0.30,
        direction="BULLISH",
    )

    mcx = _raw_evidence(
        evidence_id="mcx",
        feature="STABLE_PCR",
        value=2.75,
        direction="BULLISH",
    )

    assert classify_evidence_v1(
        index
    ) == classify_evidence_v1(
        mcx
    ) == "BULLISH"


@pytest.mark.parametrize(
    "source_authoritative",
    (
        True,
        False,
    ),
)
@pytest.mark.parametrize(
    "direction",
    (
        "BULLISH",
        "BEARISH",
    ),
)
def test_source_authoritative_is_provenance_not_directional_gate(
    source_authoritative,
    direction,
):
    evidence = _raw_evidence(
        status="AVAILABLE",
        freshness="FRESH",
        direction=direction,
        source_authoritative=source_authoritative,
    )

    assert classify_evidence_v1(
        evidence
    ) == direction


def test_policy_module_does_not_read_raw_semantic_fields():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_evaluator_policy_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    accessed = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Attribute,
        )
    }

    forbidden = {
        "feature",
        "value",
        "unit",
        "metadata",
        "strength",
        "confidence",
        "quality_score",
        "source",
    }

    assert (
        accessed
        & forbidden
    ) == set()


def test_policy_module_has_no_provider_execution_or_persistence_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_evaluator_policy_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imports.extend(
                alias.name.lower()
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imports.append(
                (
                    node.module
                    or ""
                ).lower()
            )

    forbidden = (
        "fyers",
        "smartapi",
        "requests",
        "yfinance",
        "broker",
        "execution",
        "snapshot_persistence",
        "snapshot_journal",
        "paper_orchestration",
    )

    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )


def test_policy_module_contains_no_scoring_or_pnl_policy():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_evaluator_policy_v1.py"
    )

    text = path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "weight",
        "score",
        "threshold",
        "pnl",
        "profit",
        "win_rate",
        "accuracy",
        "buy_call",
        "buy_put",
        "strike",
        "quantity",
        "target",
        "stop_loss",
    )

    assert not any(
        token in text
        for token in forbidden
    )