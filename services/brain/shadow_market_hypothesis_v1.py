"""Deterministic zero-authority market hypothesis evaluator V1.

Market hypothesis selection consumes CategoryReductionV1 states only.

AnalyzerReductionV1 values are supplied exclusively for deterministic evidence
attribution. Analyzer count and evidence count cannot change the market
hypothesis.

No execution, decision, risk, position, broker, or certification authority is
present here.
"""

from __future__ import annotations

from typing import Iterable

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
)
from services.brain.shadow_brain_v1 import (
    ShadowHypothesisV1,
)
from services.brain.shadow_reducer_v1 import (
    AnalyzerReductionV1,
    CategoryReductionV1,
    expected_category_analyzer_ids_v1,
)


CONFIDENCE_V1_DEFERRED_SENTINEL = 0.0

RESOLVED_CATEGORY_STATES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NON_DIRECTIONAL",
    }
)

UNRESOLVED_CATEGORY_STATES = frozenset(
    {
        "CONFLICT",
        "UNKNOWN",
        "MISSING",
    }
)


RATIONALE_BULLISH = (
    "MARKET_BULLISH_EXPECTED_CATEGORY_MAJORITY"
)

RATIONALE_BEARISH = (
    "MARKET_BEARISH_EXPECTED_CATEGORY_MAJORITY"
)

RATIONALE_NEUTRAL = (
    "MARKET_RESOLVED_QUORUM_WITHOUT_DIRECTIONAL_MAJORITY"
)

RATIONALE_INSUFFICIENT = (
    "MARKET_RESOLVED_QUORUM_NOT_MET"
)

RATIONALE_MISSING = (
    "MARKET_HAS_MISSING_CATEGORY"
)

RATIONALE_UNKNOWN = (
    "MARKET_HAS_UNKNOWN_CATEGORY"
)

RATIONALE_CONFLICT = (
    "MARKET_HAS_CONFLICT_CATEGORY"
)


def _require_market(
    market: object,
) -> str:
    if (
        not isinstance(
            market,
            str,
        )
        or not market.strip()
    ):
        raise ValueError(
            "market must be non-empty text."
        )

    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"Unsupported market: {market!r}."
        )

    return market


def expected_market_categories_v1(
    market: str,
) -> tuple[str, ...]:
    market = _require_market(
        market
    )

    categories = tuple(
        sorted(
            {
                descriptor.category
                for descriptor
                in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
                if (
                    descriptor.currently_consumed_by_production
                    and market
                    in descriptor.markets
                )
            }
        )
    )

    if not categories:
        raise ValueError(
            f"No production categories registered for market={market!r}."
        )

    return categories


def _revalidate_analyzer_reduction(
    reduction: AnalyzerReductionV1,
) -> AnalyzerReductionV1:
    if not isinstance(
        reduction,
        AnalyzerReductionV1,
    ):
        raise TypeError(
            "analyzer_reductions must contain "
            "AnalyzerReductionV1 values."
        )

    return AnalyzerReductionV1(
        **reduction.to_dict()
    )


def _revalidate_category_reduction(
    reduction: CategoryReductionV1,
) -> CategoryReductionV1:
    if not isinstance(
        reduction,
        CategoryReductionV1,
    ):
        raise TypeError(
            "category_reductions must contain "
            "CategoryReductionV1 values."
        )

    return CategoryReductionV1(
        **reduction.to_dict()
    )


def _market_hypothesis_from_category_states(
    states: tuple[str, ...],
) -> str:
    total = len(
        states
    )

    if total < 1:
        raise ValueError(
            "Market must have at least one expected category."
        )

    bullish = states.count(
        "BULLISH"
    )

    bearish = states.count(
        "BEARISH"
    )

    non_directional = states.count(
        "NON_DIRECTIONAL"
    )

    resolved = (
        bullish
        + bearish
        + non_directional
    )

    if bullish * 2 > total:
        return "BULLISH"

    if bearish * 2 > total:
        return "BEARISH"

    if resolved * 2 > total:
        return "NEUTRAL"

    return "INSUFFICIENT_EVIDENCE"


def _rationale_codes(
    *,
    hypothesis: str,
    category_states: tuple[str, ...],
) -> tuple[str, ...]:
    primary = {
        "BULLISH":
            RATIONALE_BULLISH,

        "BEARISH":
            RATIONALE_BEARISH,

        "NEUTRAL":
            RATIONALE_NEUTRAL,

        "INSUFFICIENT_EVIDENCE":
            RATIONALE_INSUFFICIENT,
    }[
        hypothesis
    ]

    codes = {
        primary,
    }

    if "MISSING" in category_states:
        codes.add(
            RATIONALE_MISSING
        )

    if "UNKNOWN" in category_states:
        codes.add(
            RATIONALE_UNKNOWN
        )

    if "CONFLICT" in category_states:
        codes.add(
            RATIONALE_CONFLICT
        )

    return tuple(
        sorted(
            codes
        )
    )


def _all_evidence_ids(
    reductions: tuple[
        AnalyzerReductionV1,
        ...,
    ],
) -> tuple[str, ...]:
    ids = tuple(
        evidence_id
        for reduction
        in reductions
        for evidence_id
        in reduction.evidence_ids
    )

    if len(
        set(
            ids
        )
    ) != len(
        ids
    ):
        raise ValueError(
            "Evidence IDs must be globally unique across "
            "market analyzer reductions."
        )

    return tuple(
        sorted(
            ids
        )
    )


def _attribution_ids(
    *,
    hypothesis: str,
    category_reductions: tuple[
        CategoryReductionV1,
        ...,
    ],
    analyzer_reductions: tuple[
        AnalyzerReductionV1,
        ...,
    ],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    analyzers_by_id = {
        reduction.analyzer:
            reduction
        for reduction
        in analyzer_reductions
    }

    all_ids = _all_evidence_ids(
        analyzer_reductions
    )

    if hypothesis == "INSUFFICIENT_EVIDENCE":
        return (
            (),
            (),
            all_ids,
        )

    supporting: set[str] = set()
    opposing: set[str] = set()
    unknown: set[str] = set()

    for category in category_reductions:
        category_analyzers = tuple(
            analyzers_by_id[
                analyzer_id
            ]
            for analyzer_id
            in category.present_analyzer_ids
        )

        if category.state in {
            "CONFLICT",
            "UNKNOWN",
        }:
            for analyzer in category_analyzers:
                unknown.update(
                    analyzer.evidence_ids
                )

            continue

        for analyzer in category_analyzers:
            unknown.update(
                analyzer.unknown_evidence_ids
            )

            if hypothesis == "BULLISH":
                if category.state == "BULLISH":
                    supporting.update(
                        analyzer.bullish_evidence_ids
                    )

                elif category.state == "BEARISH":
                    opposing.update(
                        analyzer.bearish_evidence_ids
                    )

            elif hypothesis == "BEARISH":
                if category.state == "BEARISH":
                    supporting.update(
                        analyzer.bearish_evidence_ids
                    )

                elif category.state == "BULLISH":
                    opposing.update(
                        analyzer.bullish_evidence_ids
                    )

            elif hypothesis == "NEUTRAL":
                if category.state == "NON_DIRECTIONAL":
                    supporting.update(
                        analyzer.non_directional_evidence_ids
                    )

                elif category.state in {
                    "BULLISH",
                    "BEARISH",
                }:
                    opposing.update(
                        analyzer.bullish_evidence_ids
                    )

                    opposing.update(
                        analyzer.bearish_evidence_ids
                    )

    #
    # Attribution completeness:
    #
    # ShadowHypothesisV1 has no fourth contextual/non-directional
    # evidence bucket. Preserve every observed evidence ID by placing
    # anything that is neither supporting nor opposing into the
    # residual unknown_evidence_ids attribution bucket.
    #
    # This is attribution-only and cannot affect market hypothesis
    # selection.
    #
    assigned = (
        supporting
        | opposing
        | unknown
    )

    residual = (
        set(
            all_ids
        )
        - assigned
    )

    unknown.update(
        residual
    )

    overlap = (
        (
            supporting
            & opposing
        )
        | (
            supporting
            & unknown
        )
        | (
            opposing
            & unknown
        )
    )

    if overlap:
        raise ValueError(
            "Hypothesis attribution evidence roles overlap: "
            f"{sorted(overlap)}"
        )

    return (
        tuple(
            sorted(
                supporting
            )
        ),
        tuple(
            sorted(
                opposing
            )
        ),
        tuple(
            sorted(
                unknown
            )
        ),
    )


def evaluate_market_hypothesis_v1(
    *,
    market: str,
    category_reductions: Iterable[
        CategoryReductionV1
    ],
    analyzer_reductions: Iterable[
        AnalyzerReductionV1
    ],
) -> ShadowHypothesisV1:
    market = _require_market(
        market
    )

    categories = tuple(
        _revalidate_category_reduction(
            reduction
        )
        for reduction
        in category_reductions
    )

    analyzers = tuple(
        _revalidate_analyzer_reduction(
            reduction
        )
        for reduction
        in analyzer_reductions
    )

    for reduction in categories:
        if reduction.market != market:
            raise ValueError(
                "Category reduction market mismatch."
            )

    for reduction in analyzers:
        if reduction.market != market:
            raise ValueError(
                "Analyzer reduction market mismatch."
            )

    category_names = tuple(
        reduction.category
        for reduction
        in categories
    )

    if len(
        set(
            category_names
        )
    ) != len(
        category_names
    ):
        raise ValueError(
            "Duplicate category reductions are not allowed."
        )

    expected_categories = (
        expected_market_categories_v1(
            market
        )
    )

    if (
        tuple(
            sorted(
                category_names
            )
        )
        != expected_categories
    ):
        raise ValueError(
            "Category reductions must exactly cover frozen "
            "production market categories."
        )

    analyzer_ids = tuple(
        reduction.analyzer
        for reduction
        in analyzers
    )

    if len(
        set(
            analyzer_ids
        )
    ) != len(
        analyzer_ids
    ):
        raise ValueError(
            "Duplicate analyzer reductions are not allowed."
        )

    analyzers_by_id = {
        reduction.analyzer:
            reduction
        for reduction
        in analyzers
    }

    expected_present_ids: set[str] = set()

    for category in categories:
        canonical_expected = (
            expected_category_analyzer_ids_v1(
                market,
                category.category,
            )
        )

        if (
            category.expected_analyzer_ids
            != canonical_expected
        ):
            raise ValueError(
                "Category expected analyzers do not match "
                "frozen registry."
            )

        expected_present_ids.update(
            category.present_analyzer_ids
        )

        actual_for_category = {
            analyzer.analyzer
            for analyzer
            in analyzers
            if analyzer.category
            == category.category
        }

        if (
            actual_for_category
            != set(
                category.present_analyzer_ids
            )
        ):
            raise ValueError(
                "Analyzer attribution set does not match "
                f"category present analyzers: {category.category!r}."
            )

    if (
        set(
            analyzer_ids
        )
        != expected_present_ids
    ):
        raise ValueError(
            "Analyzer reductions must exactly match all "
            "present analyzers declared by category reductions."
        )

    #
    # Validate all evidence IDs before hypothesis attribution.
    #
    _all_evidence_ids(
        analyzers
    )

    categories = tuple(
        sorted(
            categories,
            key=lambda item:
                item.category,
        )
    )

    analyzers = tuple(
        sorted(
            analyzers,
            key=lambda item:
                item.analyzer,
        )
    )

    states = tuple(
        category.state
        for category
        in categories
    )

    hypothesis = (
        _market_hypothesis_from_category_states(
            states
        )
    )

    (
        supporting_ids,
        opposing_ids,
        unknown_ids,
    ) = _attribution_ids(
        hypothesis=hypothesis,
        category_reductions=categories,
        analyzer_reductions=analyzers,
    )

    rationale_codes = (
        _rationale_codes(
            hypothesis=hypothesis,
            category_states=states,
        )
    )

    return ShadowHypothesisV1(
        market=market,
        hypothesis=hypothesis,
        confidence=CONFIDENCE_V1_DEFERRED_SENTINEL,
        supporting_evidence_ids=supporting_ids,
        opposing_evidence_ids=opposing_ids,
        unknown_evidence_ids=unknown_ids,
        rationale_codes=rationale_codes,
    )


__all__ = [
    "CONFIDENCE_V1_DEFERRED_SENTINEL",
    "RESOLVED_CATEGORY_STATES",
    "UNRESOLVED_CATEGORY_STATES",
    "RATIONALE_BULLISH",
    "RATIONALE_BEARISH",
    "RATIONALE_NEUTRAL",
    "RATIONALE_INSUFFICIENT",
    "RATIONALE_MISSING",
    "RATIONALE_UNKNOWN",
    "RATIONALE_CONFLICT",
    "expected_market_categories_v1",
    "evaluate_market_hypothesis_v1",
]