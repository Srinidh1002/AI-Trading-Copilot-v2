from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.brain.shadow_market_hypothesis_v1 import (
    CONFIDENCE_V1_DEFERRED_SENTINEL,
    RATIONALE_BULLISH,
    RATIONALE_BEARISH,
    RATIONALE_CONFLICT,
    RATIONALE_INSUFFICIENT,
    RATIONALE_MISSING,
    RATIONALE_NEUTRAL,
    RATIONALE_UNKNOWN,
    expected_market_categories_v1,
    evaluate_market_hypothesis_v1,
)
from services.brain.shadow_reducer_v1 import (
    AnalyzerReductionV1,
    CategoryReductionV1,
    expected_category_analyzer_ids_v1,
    reduce_category_v1,
)


def _analyzer_reduction(
    *,
    market: str,
    category: str,
    analyzer: str,
    state: str,
) -> AnalyzerReductionV1:
    prefix = (
        f"{market}:{category}:{analyzer}"
    )

    roles = {
        "BULLISH": {
            "bullish_evidence_ids": (
                f"{prefix}:bull",
            ),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
        "BEARISH": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (
                f"{prefix}:bear",
            ),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
        "NON_DIRECTIONAL": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (
                f"{prefix}:nd",
            ),
            "unknown_evidence_ids": (),
        },
        "UNKNOWN": {
            "bullish_evidence_ids": (),
            "bearish_evidence_ids": (),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (
                f"{prefix}:unknown",
            ),
        },
        "CONFLICT": {
            "bullish_evidence_ids": (
                f"{prefix}:bull",
            ),
            "bearish_evidence_ids": (
                f"{prefix}:bear",
            ),
            "non_directional_evidence_ids": (),
            "unknown_evidence_ids": (),
        },
    }[
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


def _category_for_state(
    *,
    market: str,
    category: str,
    state: str,
):
    expected = (
        expected_category_analyzer_ids_v1(
            market,
            category,
        )
    )

    if state == "MISSING":
        reductions = ()

    elif (
        state == "CONFLICT"
        and len(
            expected
        )
        >= 2
    ):
        reductions = (
            _analyzer_reduction(
                market=market,
                category=category,
                analyzer=expected[0],
                state="BULLISH",
            ),
            _analyzer_reduction(
                market=market,
                category=category,
                analyzer=expected[1],
                state="BEARISH",
            ),
        )

        for analyzer in expected[2:]:
            reductions += (
                _analyzer_reduction(
                    market=market,
                    category=category,
                    analyzer=analyzer,
                    state="UNKNOWN",
                ),
            )

    else:
        reductions = tuple(
            _analyzer_reduction(
                market=market,
                category=category,
                analyzer=analyzer,
                state=state,
            )
            for analyzer
            in expected
        )

    category_reduction = reduce_category_v1(
        market=market,
        category=category,
        analyzer_reductions=reductions,
    )

    assert (
        category_reduction.state
        == state
    )

    return (
        category_reduction,
        reductions,
    )


def _market_inputs(
    market: str,
    states: tuple[str, ...],
):
    categories = (
        expected_market_categories_v1(
            market
        )
    )

    assert (
        len(
            categories
        )
        == len(
            states
        )
    )

    category_reductions = []
    analyzer_reductions = []

    for category, state in zip(
        categories,
        states,
        strict=True,
    ):
        (
            category_reduction,
            analyzers,
        ) = _category_for_state(
            market=market,
            category=category,
            state=state,
        )

        category_reductions.append(
            category_reduction
        )

        analyzer_reductions.extend(
            analyzers
        )

    return (
        tuple(
            category_reductions
        ),
        tuple(
            analyzer_reductions
        ),
    )


def _evaluate(
    market: str,
    states: tuple[str, ...],
):
    (
        categories,
        analyzers,
    ) = _market_inputs(
        market,
        states,
    )

    return evaluate_market_hypothesis_v1(
        market=market,
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )


def test_expected_market_categories_exact_for_indices():
    expected = (
        "BREADTH",
        "EVENT",
        "EXTERNAL",
        "FLOW",
        "NEWS",
        "OPTIONS",
        "PREMARKET",
        "REGIME",
        "TECHNICAL",
        "VOLATILITY",
    )

    assert expected_market_categories_v1(
        "NIFTY"
    ) == expected

    assert expected_market_categories_v1(
        "SENSEX"
    ) == expected


@pytest.mark.parametrize(
    "market",
    (
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    ),
)
def test_expected_market_categories_exact_for_mcx(
    market,
):
    assert expected_market_categories_v1(
        market
    ) == (
        "EVENT",
        "OPTIONS",
        "POSITIONING",
        "REGIME",
        "STRUCTURE",
        "TECHNICAL",
    )


@pytest.mark.parametrize(
    "market,states,expected",
    (
        (
            "NIFTY",
            ("MISSING",) * 10,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "NIFTY",
            ("UNKNOWN",) * 10,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "NIFTY",
            ("NON_DIRECTIONAL",) * 10,
            "NEUTRAL",
        ),
        (
            "NIFTY",
            ("BULLISH",)
            + ("UNKNOWN",) * 9,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "NIFTY",
            ("BULLISH",) * 6
            + ("BEARISH",) * 4,
            "BULLISH",
        ),
        (
            "NIFTY",
            ("BULLISH",) * 4
            + ("BEARISH",) * 6,
            "BEARISH",
        ),
        (
            "NIFTY",
            ("BULLISH",) * 5
            + ("BEARISH",) * 5,
            "NEUTRAL",
        ),
        (
            "NIFTY",
            ("BULLISH",) * 6
            + ("UNKNOWN",) * 4,
            "BULLISH",
        ),
        (
            "NIFTY",
            ("BULLISH",) * 5
            + ("UNKNOWN",) * 5,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "CRUDEOILM",
            ("MISSING",) * 6,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "CRUDEOILM",
            ("UNKNOWN",) * 6,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "CRUDEOILM",
            ("NON_DIRECTIONAL",) * 6,
            "NEUTRAL",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",)
            + ("UNKNOWN",) * 5,
            "INSUFFICIENT_EVIDENCE",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",) * 4
            + ("BEARISH",) * 2,
            "BULLISH",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",) * 2
            + ("BEARISH",) * 4,
            "BEARISH",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",) * 3
            + ("BEARISH",) * 3,
            "NEUTRAL",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",) * 4
            + ("UNKNOWN",) * 2,
            "BULLISH",
        ),
        (
            "CRUDEOILM",
            ("BULLISH",) * 3
            + ("UNKNOWN",) * 3,
            "INSUFFICIENT_EVIDENCE",
        ),
    ),
)
def test_reference_market_semantics(
    market,
    states,
    expected,
):
    result = _evaluate(
        market,
        states,
    )

    assert result.hypothesis == expected
    assert result.confidence == 0.0


def test_index_resolved_quorum_without_directional_majority_is_neutral():
    result = _evaluate(
        "NIFTY",
        (
            "BULLISH",
            "MISSING",
        )
        + (
            "NON_DIRECTIONAL",
        )
        * 8,
    )

    assert result.hypothesis == "NEUTRAL"


def test_mcx_resolved_quorum_without_directional_majority_is_neutral():
    result = _evaluate(
        "GOLDM",
        (
            "BULLISH",
            "MISSING",
        )
        + (
            "NON_DIRECTIONAL",
        )
        * 4,
    )

    assert result.hypothesis == "NEUTRAL"


def test_five_resolved_index_categories_are_not_enough():
    result = _evaluate(
        "NIFTY",
        (
            "NON_DIRECTIONAL",
        )
        * 5
        + (
            "UNKNOWN",
        )
        * 5,
    )

    assert (
        result.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )


def test_six_resolved_index_categories_are_enough_for_neutral():
    result = _evaluate(
        "NIFTY",
        (
            "NON_DIRECTIONAL",
        )
        * 6
        + (
            "UNKNOWN",
        )
        * 4,
    )

    assert result.hypothesis == "NEUTRAL"


def test_three_resolved_mcx_categories_are_not_enough():
    result = _evaluate(
        "NATGASMINI",
        (
            "NON_DIRECTIONAL",
        )
        * 3
        + (
            "UNKNOWN",
        )
        * 3,
    )

    assert (
        result.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )


def test_four_resolved_mcx_categories_are_enough_for_neutral():
    result = _evaluate(
        "NATGASMINI",
        (
            "NON_DIRECTIONAL",
        )
        * 4
        + (
            "UNKNOWN",
        )
        * 2,
    )

    assert result.hypothesis == "NEUTRAL"


def test_conflict_does_not_count_as_resolved():
    result = _evaluate(
        "NIFTY",
        (
            "NON_DIRECTIONAL",
        )
        * 5
        + (
            "CONFLICT",
        )
        * 5,
    )

    assert (
        result.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )


def test_conflict_is_not_global_veto_when_directional_majority_exists():
    result = _evaluate(
        "NIFTY",
        (
            "BULLISH",
        )
        * 6
        + (
            "CONFLICT",
        )
        + (
            "UNKNOWN",
        )
        * 3,
    )

    assert result.hypothesis == "BULLISH"

    assert (
        RATIONALE_CONFLICT
        in result.rationale_codes
    )


def test_bullish_rationale_exact_primary():
    result = _evaluate(
        "CRUDEOILM",
        ("BULLISH",) * 6,
    )

    assert result.rationale_codes == (
        RATIONALE_BULLISH,
    )


def test_bearish_rationale_exact_primary():
    result = _evaluate(
        "CRUDEOILM",
        ("BEARISH",) * 6,
    )

    assert result.rationale_codes == (
        RATIONALE_BEARISH,
    )


def test_neutral_rationale_exact_primary():
    result = _evaluate(
        "CRUDEOILM",
        ("NON_DIRECTIONAL",) * 6,
    )

    assert result.rationale_codes == (
        RATIONALE_NEUTRAL,
    )


def test_insufficient_rationale_and_unresolved_presence_codes():
    result = _evaluate(
        "NIFTY",
        (
            "MISSING",
            "UNKNOWN",
            "CONFLICT",
        )
        + (
            "UNKNOWN",
        )
        * 7,
    )

    assert result.hypothesis == (
        "INSUFFICIENT_EVIDENCE"
    )

    assert result.rationale_codes == tuple(
        sorted(
            (
                RATIONALE_CONFLICT,
                RATIONALE_INSUFFICIENT,
                RATIONALE_MISSING,
                RATIONALE_UNKNOWN,
            )
        )
    )


def test_bullish_attribution_supports_bull_and_opposes_bear():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BULLISH",
        )
        * 4
        + (
            "BEARISH",
        )
        * 2,
    )

    result = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    expected_support = tuple(
        sorted(
            evidence_id
            for analyzer
            in analyzers
            if analyzer.category
            in {
                category.category
                for category
                in categories
                if category.state == "BULLISH"
            }
            for evidence_id
            in analyzer.bullish_evidence_ids
        )
    )

    expected_opposition = tuple(
        sorted(
            evidence_id
            for analyzer
            in analyzers
            if analyzer.category
            in {
                category.category
                for category
                in categories
                if category.state == "BEARISH"
            }
            for evidence_id
            in analyzer.bearish_evidence_ids
        )
    )

    assert (
        result.supporting_evidence_ids
        == expected_support
    )

    assert (
        result.opposing_evidence_ids
        == expected_opposition
    )

    assert result.unknown_evidence_ids == ()


def test_bearish_attribution_is_symmetric():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BEARISH",
        )
        * 4
        + (
            "BULLISH",
        )
        * 2,
    )

    result = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    assert result.hypothesis == "BEARISH"

    assert result.supporting_evidence_ids

    assert result.opposing_evidence_ids

    assert result.unknown_evidence_ids == ()


def test_all_non_directional_evidence_supports_neutral():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "GOLDM",
        (
            "NON_DIRECTIONAL",
        )
        * 6,
    )

    result = evaluate_market_hypothesis_v1(
        market="GOLDM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    expected_support = tuple(
        sorted(
            evidence_id
            for analyzer
            in analyzers
            for evidence_id
            in analyzer.non_directional_evidence_ids
        )
    )

    assert result.hypothesis == "NEUTRAL"

    assert (
        result.supporting_evidence_ids
        == expected_support
    )

    assert result.opposing_evidence_ids == ()
    assert result.unknown_evidence_ids == ()


def test_balanced_directional_evidence_opposes_neutral():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BULLISH",
        )
        * 3
        + (
            "BEARISH",
        )
        * 3,
    )

    result = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    all_directional = tuple(
        sorted(
            evidence_id
            for analyzer
            in analyzers
            for evidence_id
            in (
                analyzer.bullish_evidence_ids
                + analyzer.bearish_evidence_ids
            )
        )
    )

    assert result.hypothesis == "NEUTRAL"
    assert result.supporting_evidence_ids == ()

    assert (
        result.opposing_evidence_ids
        == all_directional
    )


def test_insufficient_evidence_places_all_observed_evidence_in_unknown_bucket():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "NIFTY",
        (
            "BULLISH",
        )
        * 5
        + (
            "UNKNOWN",
        )
        * 5,
    )

    result = evaluate_market_hypothesis_v1(
        market="NIFTY",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    all_ids = tuple(
        sorted(
            evidence_id
            for analyzer
            in analyzers
            for evidence_id
            in analyzer.evidence_ids
        )
    )

    assert (
        result.hypothesis
        == "INSUFFICIENT_EVIDENCE"
    )

    assert result.supporting_evidence_ids == ()
    assert result.opposing_evidence_ids == ()

    assert (
        result.unknown_evidence_ids
        == all_ids
    )


def test_conflict_category_evidence_is_unknown_at_market_level():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "NIFTY",
        (
            "BULLISH",
        )
        * 6
        + (
            "CONFLICT",
        )
        + (
            "UNKNOWN",
        )
        * 3,
    )

    result = evaluate_market_hypothesis_v1(
        market="NIFTY",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    conflict_categories = {
        category.category
        for category
        in categories
        if category.state == "CONFLICT"
    }

    conflict_ids = {
        evidence_id
        for analyzer
        in analyzers
        if analyzer.category
        in conflict_categories
        for evidence_id
        in analyzer.evidence_ids
    }

    assert result.hypothesis == "BULLISH"

    assert conflict_ids.issubset(
        set(
            result.unknown_evidence_ids
        )
    )


def test_evidence_multiplicity_cannot_change_market_hypothesis():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BULLISH",
        )
        * 4
        + (
            "BEARISH",
        )
        * 2,
    )

    baseline = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    target = analyzers[0]

    extra_ids = tuple(
        f"{target.analyzer}:extra:{index:03d}"
        for index
        in range(
            100
        )
    )

    expanded = AnalyzerReductionV1(
        market=target.market,
        analyzer=target.analyzer,
        category=target.category,
        state=target.state,
        evidence_ids=tuple(
            sorted(
                target.evidence_ids
                + extra_ids
            )
        ),
        bullish_evidence_ids=tuple(
            sorted(
                target.bullish_evidence_ids
                + extra_ids
            )
        ),
        bearish_evidence_ids=(
            target.bearish_evidence_ids
        ),
        non_directional_evidence_ids=(
            target.non_directional_evidence_ids
        ),
        unknown_evidence_ids=(
            target.unknown_evidence_ids
        ),
    )

    expanded_analyzers = (
        expanded,
    ) + tuple(
        analyzers[1:]
    )

    after = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=expanded_analyzers,
    )

    assert baseline.hypothesis == "BULLISH"
    assert after.hypothesis == "BULLISH"
    assert baseline.confidence == after.confidence == 0.0


def test_input_order_does_not_change_result():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "NIFTY",
        (
            "BULLISH",
        )
        * 6
        + (
            "UNKNOWN",
        )
        * 4,
    )

    first = evaluate_market_hypothesis_v1(
        market="NIFTY",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    second = evaluate_market_hypothesis_v1(
        market="NIFTY",
        category_reductions=tuple(
            reversed(
                categories
            )
        ),
        analyzer_reductions=tuple(
            reversed(
                analyzers
            )
        ),
    )

    assert first == second


def test_missing_category_object_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "NIFTY",
        (
            "NON_DIRECTIONAL",
        )
        * 10,
    )

    with pytest.raises(
        ValueError,
        match="exactly cover",
    ):
        evaluate_market_hypothesis_v1(
            market="NIFTY",
            category_reductions=categories[:-1],
            analyzer_reductions=analyzers[:-1],
        )


def test_duplicate_category_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "NON_DIRECTIONAL",
        )
        * 6,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate category",
    ):
        evaluate_market_hypothesis_v1(
            market="CRUDEOILM",
            category_reductions=(
                categories
                + (
                    categories[0],
                )
            ),
            analyzer_reductions=analyzers,
        )


def test_missing_present_analyzer_attribution_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "NON_DIRECTIONAL",
        )
        * 6,
    )

    with pytest.raises(
        ValueError,
        match="does not match category present analyzers|exactly match all",
    ):
        evaluate_market_hypothesis_v1(
            market="CRUDEOILM",
            category_reductions=categories,
            analyzer_reductions=analyzers[:-1],
        )


def test_extra_analyzer_attribution_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "NON_DIRECTIONAL",
        )
        * 6,
    )

    extra = analyzers[0]

    with pytest.raises(
        ValueError,
        match="Duplicate analyzer",
    ):
        evaluate_market_hypothesis_v1(
            market="CRUDEOILM",
            category_reductions=categories,
            analyzer_reductions=(
                analyzers
                + (
                    extra,
                )
            ),
        )


def test_cross_market_category_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "NIFTY",
        (
            "NON_DIRECTIONAL",
        )
        * 10,
    )

    with pytest.raises(
        ValueError,
        match="market mismatch",
    ):
        evaluate_market_hypothesis_v1(
            market="SENSEX",
            category_reductions=categories,
            analyzer_reductions=analyzers,
        )


def test_duplicate_global_evidence_id_is_rejected():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BULLISH",
        )
        * 6,
    )

    first = analyzers[0]
    second = analyzers[1]

    duplicate_id = (
        first.evidence_ids[0]
    )

    forged_second = object.__new__(
        AnalyzerReductionV1
    )

    for name, value in second.to_dict().items():
        object.__setattr__(
            forged_second,
            name,
            value,
        )

    object.__setattr__(
        forged_second,
        "evidence_ids",
        (
            duplicate_id,
        ),
    )

    object.__setattr__(
        forged_second,
        "bullish_evidence_ids",
        (
            duplicate_id,
        ),
    )

    forged = (
        analyzers[0],
        forged_second,
    ) + tuple(
        analyzers[2:]
    )

    with pytest.raises(
        ValueError
    ):
        evaluate_market_hypothesis_v1(
            market="CRUDEOILM",
            category_reductions=categories,
            analyzer_reductions=forged,
        )


@pytest.mark.parametrize(
    "market,states,expected_hypothesis",
    (
        (
            "CRUDEOILM",
            (
                "BULLISH",
                "BULLISH",
                "BULLISH",
                "BULLISH",
                "NON_DIRECTIONAL",
                "BEARISH",
            ),
            "BULLISH",
        ),
        (
            "GOLDM",
            (
                "BEARISH",
                "BEARISH",
                "BEARISH",
                "BEARISH",
                "NON_DIRECTIONAL",
                "BULLISH",
            ),
            "BEARISH",
        ),
        (
            "NATGASMINI",
            (
                "BULLISH",
                "BULLISH",
                "BULLISH",
                "BEARISH",
                "BEARISH",
                "BEARISH",
            ),
            "NEUTRAL",
        ),
        (
            "NIFTY",
            (
                "BULLISH",
            )
            * 5
            + (
                "UNKNOWN",
            )
            * 5,
            "INSUFFICIENT_EVIDENCE",
        ),
    ),
)
def test_all_observed_evidence_is_exactly_partitioned(
    market,
    states,
    expected_hypothesis,
):
    (
        categories,
        analyzers,
    ) = _market_inputs(
        market,
        states,
    )

    result = evaluate_market_hypothesis_v1(
        market=market,
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    all_ids = {
        evidence_id
        for analyzer
        in analyzers
        for evidence_id
        in analyzer.evidence_ids
    }

    supporting = set(
        result.supporting_evidence_ids
    )

    opposing = set(
        result.opposing_evidence_ids
    )

    unknown = set(
        result.unknown_evidence_ids
    )

    assert result.hypothesis == expected_hypothesis

    assert not (
        supporting
        & opposing
    )

    assert not (
        supporting
        & unknown
    )

    assert not (
        opposing
        & unknown
    )

    assert (
        supporting
        | opposing
        | unknown
    ) == all_ids


def test_non_directional_category_is_residual_unknown_for_directional_hypothesis():
    (
        categories,
        analyzers,
    ) = _market_inputs(
        "CRUDEOILM",
        (
            "BULLISH",
            "BULLISH",
            "BULLISH",
            "BULLISH",
            "NON_DIRECTIONAL",
            "BEARISH",
        ),
    )

    result = evaluate_market_hypothesis_v1(
        market="CRUDEOILM",
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    non_directional_categories = {
        category.category
        for category
        in categories
        if category.state
        == "NON_DIRECTIONAL"
    }

    non_directional_ids = {
        evidence_id
        for analyzer
        in analyzers
        if analyzer.category
        in non_directional_categories
        for evidence_id
        in analyzer.non_directional_evidence_ids
    }

    assert result.hypothesis == "BULLISH"

    assert non_directional_ids

    assert non_directional_ids.issubset(
        set(
            result.unknown_evidence_ids
        )
    )

    assert not (
        non_directional_ids
        & set(
            result.supporting_evidence_ids
        )
    )

    assert not (
        non_directional_ids
        & set(
            result.opposing_evidence_ids
        )
    )


def test_confidence_is_always_deferred_zero_for_all_four_labels():
    cases = (
        (
            "NIFTY",
            ("BULLISH",) * 10,
            "BULLISH",
        ),
        (
            "NIFTY",
            ("BEARISH",) * 10,
            "BEARISH",
        ),
        (
            "NIFTY",
            ("NON_DIRECTIONAL",) * 10,
            "NEUTRAL",
        ),
        (
            "NIFTY",
            ("UNKNOWN",) * 10,
            "INSUFFICIENT_EVIDENCE",
        ),
    )

    for market, states, expected in cases:
        result = _evaluate(
            market,
            states,
        )

        assert result.hypothesis == expected

        assert (
            result.confidence
            == CONFIDENCE_V1_DEFERRED_SENTINEL
            == 0.0
        )


def test_market_module_has_no_trade_execution_or_provider_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_market_hypothesis_v1.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
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
                for alias
                in node.names
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
        for module
        in imports
        for token
        in forbidden
    )


def test_market_module_contains_no_trade_action_or_pnl_policy():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "brain"
        / "shadow_market_hypothesis_v1.py"
    )

    text = path.read_text(
        encoding="utf-8"
    ).lower()

    forbidden = (
        "buy_call",
        "buy_put",
        "strike_selection",
        "quantity_selection",
        "stop_loss",
        "target_1",
        "target_2",
        "target_3",
        "win_rate",
        "profit_factor",
        "pnl",
    )

    assert not any(
        token in text
        for token
        in forbidden
    )