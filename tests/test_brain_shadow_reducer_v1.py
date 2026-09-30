from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.brain.shadow_reducer_v1 import (
    ANALYZER_REDUCER_STATES,
    CATEGORY_REDUCER_STATES,
    AnalyzerReductionV1,
    CategoryReductionV1,
    expected_category_analyzer_ids_v1,
    reduce_analyzer_result_v1,
    reduce_category_v1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)


NOW = datetime(
    2026,
    9,
    30,
    10,
    0,
    tzinfo=timezone.utc,
)


def _evidence(
    *,
    evidence_id: str,
    direction: str,
    status: str = "AVAILABLE",
    freshness: str = "FRESH",
) -> EvidenceV1:
    evidence = object.__new__(
        EvidenceV1
    )

    values = {
        "evidence_id": evidence_id,
        "market": "NIFTY",
        "analyzer": "index.mtf.legacy_v1",
        "analyzer_version": "1.0",
        "category": "TECHNICAL",
        "feature": "TEST",
        "observed_at": NOW,
        "generated_at": NOW,
        "status": status,
        "freshness": freshness,
        "source": "REDUCER_TEST",
        "value": 1.0,
        "unit": "TEST",
        "direction": direction,
        "strength": 0.5,
        "confidence": 0.5,
        "quality_score": 1.0,
        "source_authoritative": True,
        "missing_reason": None,
        "blockers": (),
        "warnings": (),
        "metadata": (),
        "schema_version": "REDUCER_TEST",
    }

    for name, value in values.items():
        object.__setattr__(
            evidence,
            name,
            value,
        )

    return evidence


def _result(
    *,
    analyzer: str = "index.mtf.legacy_v1",
    market: str = "NIFTY",
    status: str = "OK",
    evidence: tuple[EvidenceV1, ...] = (),
) -> AnalyzerResultV1:
    result = object.__new__(
        AnalyzerResultV1
    )

    values = {
        "result_id": (
            f"{market}:{analyzer}:test"
        ),
        "market": market,
        "analyzer": analyzer,
        "analyzer_version": "1.0",
        "generated_at": NOW,
        "status": status,
        "evidence": evidence,
        "blockers": (),
        "warnings": (),
        "execution_authority": False,
        "schema_version": "REDUCER_TEST",
    }

    for name, value in values.items():
        object.__setattr__(
            result,
            name,
            value,
        )

    return result


def _reduction(
    *,
    analyzer: str,
    category: str,
    state: str,
    market: str = "NIFTY",
) -> AnalyzerReductionV1:
    role_map = {
        "BULLISH": {
            "bullish_evidence_ids": (
                f"{analyzer}:bull",
            ),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
        "BEARISH": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (
                f"{analyzer}:bear",
            ),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
        "NON_DIRECTIONAL": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (
                f"{analyzer}:nd",
            ),
            "unknown_evidence_ids": (),
        },
        "UNKNOWN": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (
                f"{analyzer}:unknown",
            ),
        },
        "CONFLICT": {
            "bullish_evidence_ids": (
                f"{analyzer}:bull",
            ),
            "bearish_evidence_ids": (
                f"{analyzer}:bear",
            ),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
    }

    roles = role_map[
        state
    ]

    evidence_ids = tuple(
        sorted(
            evidence_id
            for values
            in roles.values()
            for evidence_id
            in values
        )
    )

    return AnalyzerReductionV1(
        market=market,
        analyzer=analyzer,
        category=category,
        state=state,
        evidence_ids=evidence_ids,
        **roles,
    )


def test_reducer_state_vocabularies_are_exact():
    assert ANALYZER_REDUCER_STATES == frozenset(
        {
            "BULLISH",
            "BEARISH",
            "NON_DIRECTIONAL",
            "CONFLICT",
            "UNKNOWN",
        }
    )

    assert CATEGORY_REDUCER_STATES == frozenset(
        {
            "BULLISH",
            "BEARISH",
            "NON_DIRECTIONAL",
            "CONFLICT",
            "UNKNOWN",
            "MISSING",
        }
    )


@pytest.mark.parametrize(
    "direction,expected",
    (
        ("BULLISH", "BULLISH"),
        ("BEARISH", "BEARISH"),
        ("NEUTRAL", "NON_DIRECTIONAL"),
        ("MIXED", "NON_DIRECTIONAL"),
        ("UNKNOWN", "UNKNOWN"),
    ),
)
def test_single_evidence_analyzer_reduction(
    direction,
    expected,
):
    result = _result(
        evidence=(
            _evidence(
                evidence_id="e1",
                direction=direction,
            ),
        ),
    )

    reduced = reduce_analyzer_result_v1(
        result
    )

    assert reduced.state == expected
    assert reduced.market == "NIFTY"
    assert reduced.analyzer == "index.mtf.legacy_v1"
    assert reduced.category == "TECHNICAL"


def test_analyzer_empty_evidence_is_unknown():
    reduced = reduce_analyzer_result_v1(
        _result(
            evidence=(),
        )
    )

    assert reduced.state == "UNKNOWN"
    assert reduced.evidence_ids == ()


def test_analyzer_same_side_duplication_has_no_state_weight():
    reduced = reduce_analyzer_result_v1(
        _result(
            evidence=(
                _evidence(
                    evidence_id="a",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="b",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="c",
                    direction="BULLISH",
                ),
            ),
        )
    )

    assert reduced.state == "BULLISH"
    assert reduced.bullish_evidence_ids == (
        "a",
        "b",
        "c",
    )


def test_analyzer_opposing_direction_is_conflict_even_with_bull_majority():
    reduced = reduce_analyzer_result_v1(
        _result(
            evidence=(
                _evidence(
                    evidence_id="a",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="b",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="c",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="z",
                    direction="BEARISH",
                ),
            ),
        )
    )

    assert reduced.state == "CONFLICT"


def test_analyzer_direction_survives_non_directional_and_unknown():
    reduced = reduce_analyzer_result_v1(
        _result(
            evidence=(
                _evidence(
                    evidence_id="bull",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="neutral",
                    direction="NEUTRAL",
                ),
                _evidence(
                    evidence_id="unverified",
                    direction="BEARISH",
                    status="UNVERIFIED",
                ),
            ),
        )
    )

    assert reduced.state == "BULLISH"

    assert reduced.bullish_evidence_ids == (
        "bull",
    )

    assert reduced.non_directional_evidence_ids == (
        "neutral",
    )

    assert reduced.unknown_evidence_ids == (
        "unverified",
    )


@pytest.mark.parametrize(
    "result_status",
    (
        "ERROR",
        "UNAVAILABLE",
    ),
)
def test_non_evaluable_analyzer_becomes_unknown(
    result_status,
):
    reduced = reduce_analyzer_result_v1(
        _result(
            status=result_status,
            evidence=(
                _evidence(
                    evidence_id="bull",
                    direction="BULLISH",
                ),
            ),
        )
    )

    assert reduced.state == "UNKNOWN"

    assert reduced.unknown_evidence_ids == (
        "bull",
    )


def test_analyzer_evidence_ids_are_deterministically_sorted():
    reduced = reduce_analyzer_result_v1(
        _result(
            evidence=(
                _evidence(
                    evidence_id="z",
                    direction="BEARISH",
                ),
                _evidence(
                    evidence_id="a",
                    direction="BULLISH",
                ),
                _evidence(
                    evidence_id="m",
                    direction="NEUTRAL",
                ),
            ),
        )
    )

    assert reduced.evidence_ids == (
        "a",
        "m",
        "z",
    )


def test_unknown_analyzer_is_rejected():
    result = _result(
        analyzer="unknown.fake.v1",
        evidence=(),
    )

    with pytest.raises(
        ValueError,
        match="not exactly one production analyzer",
    ):
        reduce_analyzer_result_v1(
            result
        )


def test_analyzer_wrong_type_rejected():
    with pytest.raises(
        TypeError,
        match="result must be AnalyzerResultV1",
    ):
        reduce_analyzer_result_v1(
            object()
        )


def test_expected_category_analyzers_nifty_premarket_exact():
    assert expected_category_analyzer_ids_v1(
        "NIFTY",
        "PREMARKET",
    ) == (
        "index.gap.legacy_v1",
        "index.previous_session.legacy_v1",
    )


@pytest.mark.parametrize(
    "market",
    (
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    ),
)
def test_expected_mcx_technical_analyzer_exact(
    market,
):
    assert expected_category_analyzer_ids_v1(
        market,
        "TECHNICAL",
    ) == (
        "mcx.mtf.native_v1",
    )


def test_unknown_category_rejected():
    with pytest.raises(
        ValueError,
        match="No production analyzers registered",
    ):
        expected_category_analyzer_ids_v1(
            "NIFTY",
            "DOES_NOT_EXIST",
        )


def test_category_all_missing():
    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=(),
    )

    assert reduced.state == "MISSING"

    assert reduced.coverage_complete is False

    assert reduced.present_analyzer_ids == ()

    assert reduced.missing_analyzer_ids == (
        "index.gap.legacy_v1",
        "index.previous_session.legacy_v1",
    )


def test_category_premarket_both_bullish():
    reductions = (
        _reduction(
            analyzer="index.gap.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
        ),
        _reduction(
            analyzer="index.previous_session.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
        ),
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=reductions,
    )

    assert reduced.state == "BULLISH"
    assert reduced.coverage_complete is True


def test_category_premarket_directional_disagreement_is_conflict():
    reductions = (
        _reduction(
            analyzer="index.gap.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
        ),
        _reduction(
            analyzer="index.previous_session.legacy_v1",
            category="PREMARKET",
            state="BEARISH",
        ),
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=reductions,
    )

    assert reduced.state == "CONFLICT"


def test_category_conflict_analyzer_has_precedence():
    reductions = (
        _reduction(
            analyzer="index.gap.legacy_v1",
            category="PREMARKET",
            state="CONFLICT",
        ),
        _reduction(
            analyzer="index.previous_session.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
        ),
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=reductions,
    )

    assert reduced.state == "CONFLICT"

    assert reduced.conflict_analyzer_ids == (
        "index.gap.legacy_v1",
    )


@pytest.mark.parametrize(
    "state",
    (
        "BULLISH",
        "BEARISH",
        "NON_DIRECTIONAL",
        "UNKNOWN",
    ),
)
def test_partial_premarket_preserves_state_and_missing_coverage(
    state,
):
    reduction = _reduction(
        analyzer="index.gap.legacy_v1",
        category="PREMARKET",
        state=state,
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=(
            reduction,
        ),
    )

    assert reduced.state == state
    assert reduced.coverage_complete is False

    assert reduced.missing_analyzer_ids == (
        "index.previous_session.legacy_v1",
    )


def test_category_unknown_does_not_cancel_bullish():
    reductions = (
        _reduction(
            analyzer="index.gap.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
        ),
        _reduction(
            analyzer="index.previous_session.legacy_v1",
            category="PREMARKET",
            state="UNKNOWN",
        ),
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=reductions,
    )

    assert reduced.state == "BULLISH"


def test_category_non_directional_does_not_cancel_bearish():
    reductions = (
        _reduction(
            analyzer="index.gap.legacy_v1",
            category="PREMARKET",
            state="BEARISH",
        ),
        _reduction(
            analyzer="index.previous_session.legacy_v1",
            category="PREMARKET",
            state="NON_DIRECTIONAL",
        ),
    )

    reduced = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=reductions,
    )

    assert reduced.state == "BEARISH"


def test_category_reduction_is_input_order_invariant():
    left = _reduction(
        analyzer="index.gap.legacy_v1",
        category="PREMARKET",
        state="BULLISH",
    )

    right = _reduction(
        analyzer="index.previous_session.legacy_v1",
        category="PREMARKET",
        state="UNKNOWN",
    )

    first = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=(
            left,
            right,
        ),
    )

    second = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=(
            right,
            left,
        ),
    )

    assert first == second


def test_duplicate_analyzer_reduction_rejected():
    reduction = _reduction(
        analyzer="index.gap.legacy_v1",
        category="PREMARKET",
        state="BULLISH",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate analyzer reductions",
    ):
        reduce_category_v1(
            market="NIFTY",
            category="PREMARKET",
            analyzer_reductions=(
                reduction,
                reduction,
            ),
        )


def test_unexpected_forged_analyzer_for_category_rejected():
    reduction = object.__new__(
        AnalyzerReductionV1
    )

    object.__setattr__(
        reduction,
        "market",
        "NIFTY",
    )

    object.__setattr__(
        reduction,
        "analyzer",
        "index.mtf.legacy_v1",
    )

    object.__setattr__(
        reduction,
        "category",
        "PREMARKET",
    )

    object.__setattr__(
        reduction,
        "state",
        "BULLISH",
    )

    with pytest.raises(
        ValueError,
        match="Unexpected analyzer reductions",
    ):
        reduce_category_v1(
            market="NIFTY",
            category="PREMARKET",
            analyzer_reductions=(
                reduction,
            ),
        )


def test_cross_market_reduction_rejected():
    reduction = _reduction(
        analyzer="index.gap.legacy_v1",
        category="PREMARKET",
        state="BULLISH",
        market="SENSEX",
    )

    with pytest.raises(
        ValueError,
        match="market mismatch",
    ):
        reduce_category_v1(
            market="NIFTY",
            category="PREMARKET",
            analyzer_reductions=(
                reduction,
            ),
        )


def test_cross_category_reduction_rejected():
    reduction = _reduction(
        analyzer="index.mtf.legacy_v1",
        category="TECHNICAL",
        state="BULLISH",
    )

    with pytest.raises(
        ValueError,
        match="category mismatch",
    ):
        reduce_category_v1(
            market="NIFTY",
            category="PREMARKET",
            analyzer_reductions=(
                reduction,
            ),
        )


def test_reduce_category_has_no_expected_analyzer_override():
    signature = inspect.signature(
        reduce_category_v1
    )

    assert (
        "expected_analyzer_ids"
        not in signature.parameters
    )


def test_analyzer_contract_is_frozen():
    reduction = _reduction(
        analyzer="index.mtf.legacy_v1",
        category="TECHNICAL",
        state="BULLISH",
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        reduction.state = "BEARISH"


def test_category_contract_is_frozen():
    reduction = reduce_category_v1(
        market="NIFTY",
        category="PREMARKET",
        analyzer_reductions=(),
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        reduction.state = "BULLISH"


def test_analyzer_direct_constructor_rejects_inconsistent_state():
    with pytest.raises(
        ValueError,
        match="inconsistent",
    ):
        AnalyzerReductionV1(
            market="NIFTY",
            analyzer="index.mtf.legacy_v1",
            category="TECHNICAL",
            state="BEARISH",
            evidence_ids=(
                "e1",
            ),
            bullish_evidence_ids=(
                "e1",
            ),
            bearish_evidence_ids=(),
            non_directional_evidence_ids=(),
            unknown_evidence_ids=(),
        )


def test_analyzer_direct_constructor_rejects_fake_registry_analyzer():
    with pytest.raises(
        ValueError,
        match="not exactly one production analyzer",
    ):
        AnalyzerReductionV1(
            market="NIFTY",
            analyzer="fake.analyzer.v1",
            category="TECHNICAL",
            state="BULLISH",
            evidence_ids=(
                "e1",
            ),
            bullish_evidence_ids=(
                "e1",
            ),
            bearish_evidence_ids=(),
            non_directional_evidence_ids=(),
            unknown_evidence_ids=(),
        )


def test_analyzer_direct_constructor_rejects_registry_category_mismatch():
    with pytest.raises(
        ValueError,
        match="does not match frozen production registry",
    ):
        AnalyzerReductionV1(
            market="NIFTY",
            analyzer="index.mtf.legacy_v1",
            category="PREMARKET",
            state="BULLISH",
            evidence_ids=(
                "e1",
            ),
            bullish_evidence_ids=(
                "e1",
            ),
            bearish_evidence_ids=(),
            non_directional_evidence_ids=(),
            unknown_evidence_ids=(),
        )


@pytest.mark.parametrize(
    "expected_analyzer_ids",
    (
        (
            "fake.analyzer.v1",
        ),
        (
            "index.gap.legacy_v1",
        ),
    ),
)
def test_category_direct_constructor_requires_exact_registry_expectation(
    expected_analyzer_ids,
):
    with pytest.raises(
        ValueError,
        match="exactly match frozen production registry",
    ):
        CategoryReductionV1(
            market="NIFTY",
            category="PREMARKET",
            state="MISSING",
            expected_analyzer_ids=expected_analyzer_ids,
            present_analyzer_ids=(),
            missing_analyzer_ids=expected_analyzer_ids,
            bullish_analyzer_ids=(),
            bearish_analyzer_ids=(),
            non_directional_analyzer_ids=(),
            conflict_analyzer_ids=(),
            unknown_analyzer_ids=(),
            coverage_complete=False,
        )


def test_category_direct_constructor_rejects_bad_missing_partition():
    with pytest.raises(
        ValueError,
        match="missing_analyzer_ids",
    ):
        CategoryReductionV1(
            market="NIFTY",
            category="PREMARKET",
            state="MISSING",
            expected_analyzer_ids=(
                "index.gap.legacy_v1",
                "index.previous_session.legacy_v1",
            ),
            present_analyzer_ids=(),
            missing_analyzer_ids=(
                "index.gap.legacy_v1",
            ),
            bullish_analyzer_ids=(),
            bearish_analyzer_ids=(),
            non_directional_analyzer_ids=(),
            conflict_analyzer_ids=(),
            unknown_analyzer_ids=(),
            coverage_complete=False,
        )


def test_category_direct_constructor_rejects_role_overlap():
    with pytest.raises(
        ValueError,
        match="overlap",
    ):
        CategoryReductionV1(
            market="NIFTY",
            category="TECHNICAL",
            state="CONFLICT",
            expected_analyzer_ids=(
                "index.mtf.legacy_v1",
            ),
            present_analyzer_ids=(
                "index.mtf.legacy_v1",
            ),
            missing_analyzer_ids=(),
            bullish_analyzer_ids=(
                "index.mtf.legacy_v1",
            ),
            bearish_analyzer_ids=(
                "index.mtf.legacy_v1",
            ),
            non_directional_analyzer_ids=(),
            conflict_analyzer_ids=(),
            unknown_analyzer_ids=(),
            coverage_complete=True,
        )


def test_reducer_contracts_contain_no_trade_authority_fields():
    names = {
        field.name
        for cls in (
            AnalyzerReductionV1,
            CategoryReductionV1,
        )
        for field
        in fields(
            cls
        )
    }

    forbidden = {
        "action",
        "order",
        "broker",
        "strike",
        "quantity",
        "qty",
        "stop_loss",
        "sl",
        "target",
        "pnl",
        "profit",
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    }

    assert not (
        names
        & forbidden
    )


def test_reducer_module_does_not_define_market_hypothesis_formula():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_reducer_v1.py"
    )

    text = path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "market_bullish_threshold",
        "market_bearish_threshold",
        "category_weight",
        "confidence_formula",
        "buy_call",
        "buy_put",
    )

    assert not any(
        token in text
        for token in forbidden
    )


def test_reducer_module_has_no_provider_broker_or_execution_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_reducer_v1.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    imports = []

    for node in ast.walk(
        tree
    ):
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
        "paper_orchestration",
        "snapshot_persistence",
        "snapshot_journal",
    )

    assert not any(
        token in module
        for module in imports
        for token in forbidden
    )