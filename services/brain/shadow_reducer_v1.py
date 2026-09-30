"""Deterministic zero-authority Shadow Brain reducers V1.

This module implements only:

EvidenceV1
    -> AnalyzerReductionV1
    -> CategoryReductionV1

Market-level hypothesis aggregation is deliberately outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterable

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
)
from services.brain.shadow_evaluator_policy_v1 import (
    classify_analyzer_result_v1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
)


ANALYZER_REDUCTION_SCHEMA_V1 = (
    "BRAIN_SHADOW_ANALYZER_REDUCTION_V1"
)

CATEGORY_REDUCTION_SCHEMA_V1 = (
    "BRAIN_SHADOW_CATEGORY_REDUCTION_V1"
)

ANALYZER_REDUCER_STATES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NON_DIRECTIONAL",
        "CONFLICT",
        "UNKNOWN",
    }
)

CATEGORY_REDUCER_STATES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NON_DIRECTIONAL",
        "CONFLICT",
        "UNKNOWN",
        "MISSING",
    }
)


def _require_text(
    value: object,
    *,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        raise ValueError(
            f"{name} must be non-empty text."
        )

    return value


def _require_sorted_unique_text_tuple(
    value: object,
    *,
    name: str,
) -> tuple[str, ...]:
    if not isinstance(
        value,
        tuple,
    ):
        raise ValueError(
            f"{name} must be a tuple."
        )

    for item in value:
        _require_text(
            item,
            name=f"{name} item",
        )

    if tuple(
        sorted(
            value
        )
    ) != value:
        raise ValueError(
            f"{name} must be sorted."
        )

    if len(
        set(
            value
        )
    ) != len(
        value
    ):
        raise ValueError(
            f"{name} must contain unique values."
        )

    return value


def _assert_disjoint(
    groups: tuple[
        tuple[str, ...],
        ...,
    ],
    *,
    name: str,
) -> None:
    seen: set[str] = set()

    for group in groups:
        overlap = (
            seen
            & set(
                group
            )
        )

        if overlap:
            raise ValueError(
                f"{name} groups overlap: {sorted(overlap)}"
            )

        seen.update(
            group
        )


def _production_descriptor(
    *,
    market: str,
    analyzer: str,
):
    matches = tuple(
        descriptor
        for descriptor
        in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
        if (
            descriptor.analyzer_id
            == analyzer
            and descriptor.currently_consumed_by_production
            and market
            in descriptor.markets
        )
    )

    if len(
        matches
    ) != 1:
        raise ValueError(
            "Analyzer is not exactly one production analyzer "
            f"for market: market={market!r}, analyzer={analyzer!r}."
        )

    return matches[
        0
    ]


def expected_category_analyzer_ids_v1(
    market: str,
    category: str,
) -> tuple[str, ...]:
    _require_text(
        market,
        name="market",
    )

    _require_text(
        category,
        name="category",
    )

    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"Unsupported market: {market!r}."
        )

    analyzer_ids = tuple(
        sorted(
            descriptor.analyzer_id
            for descriptor
            in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
            if (
                descriptor.currently_consumed_by_production
                and market
                in descriptor.markets
                and descriptor.category
                == category
            )
        )
    )

    if not analyzer_ids:
        raise ValueError(
            "No production analyzers registered for "
            f"market={market!r}, category={category!r}."
        )

    return analyzer_ids


@dataclass(
    frozen=True,
    slots=True,
)
class AnalyzerReductionV1:
    market: str
    analyzer: str
    category: str
    state: str

    evidence_ids: tuple[str, ...]

    bullish_evidence_ids: tuple[str, ...]
    bearish_evidence_ids: tuple[str, ...]
    non_directional_evidence_ids: tuple[str, ...]
    unknown_evidence_ids: tuple[str, ...]

    schema_version: str = (
        ANALYZER_REDUCTION_SCHEMA_V1
    )

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.market,
            name="market",
        )

        _require_text(
            self.analyzer,
            name="analyzer",
        )

        _require_text(
            self.category,
            name="category",
        )

        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"Unsupported market: {self.market!r}."
            )

        descriptor = _production_descriptor(
            market=self.market,
            analyzer=self.analyzer,
        )

        if descriptor.category != self.category:
            raise ValueError(
                "Analyzer reduction category does not match "
                "frozen production registry."
            )

        if self.state not in ANALYZER_REDUCER_STATES:
            raise ValueError(
                f"Invalid analyzer reducer state: {self.state!r}."
            )

        if (
            self.schema_version
            != ANALYZER_REDUCTION_SCHEMA_V1
        ):
            raise ValueError(
                "Invalid analyzer reduction schema version."
            )

        tuple_fields = (
            "evidence_ids",
            "bullish_evidence_ids",
            "bearish_evidence_ids",
            "non_directional_evidence_ids",
            "unknown_evidence_ids",
        )

        for field_name in tuple_fields:
            _require_sorted_unique_text_tuple(
                getattr(
                    self,
                    field_name,
                ),
                name=field_name,
            )

        role_groups = (
            self.bullish_evidence_ids,
            self.bearish_evidence_ids,
            self.non_directional_evidence_ids,
            self.unknown_evidence_ids,
        )

        _assert_disjoint(
            role_groups,
            name="analyzer evidence role",
        )

        role_union = tuple(
            sorted(
                {
                    evidence_id
                    for group
                    in role_groups
                    for evidence_id
                    in group
                }
            )
        )

        if (
            role_union
            != self.evidence_ids
        ):
            raise ValueError(
                "Analyzer evidence role IDs must exactly "
                "partition evidence_ids."
            )

        expected_state = _analyzer_state_from_roles(
            bullish_ids=self.bullish_evidence_ids,
            bearish_ids=self.bearish_evidence_ids,
            non_directional_ids=self.non_directional_evidence_ids,
        )

        if (
            self.state
            != expected_state
        ):
            raise ValueError(
                "Analyzer reduction state is inconsistent "
                "with evidence roles."
            )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            field.name:
                getattr(
                    self,
                    field.name,
                )
            for field
            in fields(
                self
            )
        }


@dataclass(
    frozen=True,
    slots=True,
)
class CategoryReductionV1:
    market: str
    category: str
    state: str

    expected_analyzer_ids: tuple[str, ...]
    present_analyzer_ids: tuple[str, ...]
    missing_analyzer_ids: tuple[str, ...]

    bullish_analyzer_ids: tuple[str, ...]
    bearish_analyzer_ids: tuple[str, ...]
    non_directional_analyzer_ids: tuple[str, ...]
    conflict_analyzer_ids: tuple[str, ...]
    unknown_analyzer_ids: tuple[str, ...]

    coverage_complete: bool

    schema_version: str = (
        CATEGORY_REDUCTION_SCHEMA_V1
    )

    def __post_init__(
        self,
    ) -> None:
        _require_text(
            self.market,
            name="market",
        )

        _require_text(
            self.category,
            name="category",
        )

        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"Unsupported market: {self.market!r}."
            )

        if self.state not in CATEGORY_REDUCER_STATES:
            raise ValueError(
                f"Invalid category reducer state: {self.state!r}."
            )

        if (
            self.schema_version
            != CATEGORY_REDUCTION_SCHEMA_V1
        ):
            raise ValueError(
                "Invalid category reduction schema version."
            )

        if not isinstance(
            self.coverage_complete,
            bool,
        ):
            raise ValueError(
                "coverage_complete must be bool."
            )

        tuple_fields = (
            "expected_analyzer_ids",
            "present_analyzer_ids",
            "missing_analyzer_ids",
            "bullish_analyzer_ids",
            "bearish_analyzer_ids",
            "non_directional_analyzer_ids",
            "conflict_analyzer_ids",
            "unknown_analyzer_ids",
        )

        for field_name in tuple_fields:
            _require_sorted_unique_text_tuple(
                getattr(
                    self,
                    field_name,
                ),
                name=field_name,
            )

        canonical_expected = (
            expected_category_analyzer_ids_v1(
                self.market,
                self.category,
            )
        )

        if (
            self.expected_analyzer_ids
            != canonical_expected
        ):
            raise ValueError(
                "expected_analyzer_ids must exactly match "
                "frozen production registry."
            )

        expected = set(
            self.expected_analyzer_ids
        )

        present = set(
            self.present_analyzer_ids
        )

        missing = set(
            self.missing_analyzer_ids
        )

        if not present.issubset(
            expected
        ):
            raise ValueError(
                "present_analyzer_ids must be a subset "
                "of expected_analyzer_ids."
            )

        if (
            missing
            != (
                expected
                - present
            )
        ):
            raise ValueError(
                "missing_analyzer_ids must exactly equal "
                "expected minus present."
            )

        role_groups = (
            self.bullish_analyzer_ids,
            self.bearish_analyzer_ids,
            self.non_directional_analyzer_ids,
            self.conflict_analyzer_ids,
            self.unknown_analyzer_ids,
        )

        _assert_disjoint(
            role_groups,
            name="category analyzer role",
        )

        role_union = {
            analyzer_id
            for group
            in role_groups
            for analyzer_id
            in group
        }

        if (
            role_union
            != present
        ):
            raise ValueError(
                "Category analyzer role IDs must exactly "
                "partition present_analyzer_ids."
            )

        expected_complete = (
            not self.missing_analyzer_ids
        )

        if (
            self.coverage_complete
            is not expected_complete
        ):
            raise ValueError(
                "coverage_complete is inconsistent "
                "with missing_analyzer_ids."
            )

        expected_state = _category_state_from_roles(
            present_ids=self.present_analyzer_ids,
            bullish_ids=self.bullish_analyzer_ids,
            bearish_ids=self.bearish_analyzer_ids,
            non_directional_ids=self.non_directional_analyzer_ids,
            conflict_ids=self.conflict_analyzer_ids,
        )

        if (
            self.state
            != expected_state
        ):
            raise ValueError(
                "Category reduction state is inconsistent "
                "with analyzer roles."
            )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            field.name:
                getattr(
                    self,
                    field.name,
                )
            for field
            in fields(
                self
            )
        }


def _analyzer_state_from_roles(
    *,
    bullish_ids: tuple[str, ...],
    bearish_ids: tuple[str, ...],
    non_directional_ids: tuple[str, ...],
) -> str:
    if (
        bullish_ids
        and bearish_ids
    ):
        return "CONFLICT"

    if bullish_ids:
        return "BULLISH"

    if bearish_ids:
        return "BEARISH"

    if non_directional_ids:
        return "NON_DIRECTIONAL"

    return "UNKNOWN"


def _category_state_from_roles(
    *,
    present_ids: tuple[str, ...],
    bullish_ids: tuple[str, ...],
    bearish_ids: tuple[str, ...],
    non_directional_ids: tuple[str, ...],
    conflict_ids: tuple[str, ...],
) -> str:
    if not present_ids:
        return "MISSING"

    if conflict_ids:
        return "CONFLICT"

    if (
        bullish_ids
        and bearish_ids
    ):
        return "CONFLICT"

    if bullish_ids:
        return "BULLISH"

    if bearish_ids:
        return "BEARISH"

    if non_directional_ids:
        return "NON_DIRECTIONAL"

    return "UNKNOWN"


def reduce_analyzer_result_v1(
    result: AnalyzerResultV1,
) -> AnalyzerReductionV1:
    if not isinstance(
        result,
        AnalyzerResultV1,
    ):
        raise TypeError(
            "result must be AnalyzerResultV1."
        )

    descriptor = _production_descriptor(
        market=result.market,
        analyzer=result.analyzer,
    )

    classifications = (
        classify_analyzer_result_v1(
            result
        )
    )

    evidence_ids = tuple(
        evidence_id
        for (
            evidence_id,
            _state,
        )
        in classifications
    )

    bullish_ids = tuple(
        evidence_id
        for (
            evidence_id,
            state,
        )
        in classifications
        if state
        == "BULLISH"
    )

    bearish_ids = tuple(
        evidence_id
        for (
            evidence_id,
            state,
        )
        in classifications
        if state
        == "BEARISH"
    )

    non_directional_ids = tuple(
        evidence_id
        for (
            evidence_id,
            state,
        )
        in classifications
        if state
        == "NON_DIRECTIONAL"
    )

    unknown_ids = tuple(
        evidence_id
        for (
            evidence_id,
            state,
        )
        in classifications
        if state
        == "UNKNOWN"
    )

    state = _analyzer_state_from_roles(
        bullish_ids=bullish_ids,
        bearish_ids=bearish_ids,
        non_directional_ids=non_directional_ids,
    )

    return AnalyzerReductionV1(
        market=result.market,
        analyzer=result.analyzer,
        category=descriptor.category,
        state=state,
        evidence_ids=evidence_ids,
        bullish_evidence_ids=bullish_ids,
        bearish_evidence_ids=bearish_ids,
        non_directional_evidence_ids=non_directional_ids,
        unknown_evidence_ids=unknown_ids,
    )


def reduce_category_v1(
    *,
    market: str,
    category: str,
    analyzer_reductions: Iterable[
        AnalyzerReductionV1
    ],
) -> CategoryReductionV1:
    _require_text(
        market,
        name="market",
    )

    _require_text(
        category,
        name="category",
    )

    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"Unsupported market: {market!r}."
        )

    reductions = tuple(
        analyzer_reductions
    )

    for reduction in reductions:
        if not isinstance(
            reduction,
            AnalyzerReductionV1,
        ):
            raise TypeError(
                "analyzer_reductions must contain "
                "AnalyzerReductionV1 values."
            )

        if (
            reduction.market
            != market
        ):
            raise ValueError(
                "Analyzer reduction market mismatch."
            )

        if (
            reduction.category
            != category
        ):
            raise ValueError(
                "Analyzer reduction category mismatch."
            )

    analyzer_ids = tuple(
        reduction.analyzer
        for reduction
        in reductions
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

    expected = (
        expected_category_analyzer_ids_v1(
            market,
            category,
        )
    )

    expected_set = set(
        expected
    )

    unexpected = (
        set(
            analyzer_ids
        )
        - expected_set
    )

    if unexpected:
        raise ValueError(
            "Unexpected analyzer reductions for category: "
            f"{sorted(unexpected)}"
        )

    by_state: dict[
        str,
        list[str],
    ] = {
        "BULLISH": [],
        "BEARISH": [],
        "NON_DIRECTIONAL": [],
        "CONFLICT": [],
        "UNKNOWN": [],
    }

    for reduction in reductions:
        by_state[
            reduction.state
        ].append(
            reduction.analyzer
        )

    present = tuple(
        sorted(
            analyzer_ids
        )
    )

    missing = tuple(
        sorted(
            expected_set
            - set(
                present
            )
        )
    )

    bullish = tuple(
        sorted(
            by_state[
                "BULLISH"
            ]
        )
    )

    bearish = tuple(
        sorted(
            by_state[
                "BEARISH"
            ]
        )
    )

    non_directional = tuple(
        sorted(
            by_state[
                "NON_DIRECTIONAL"
            ]
        )
    )

    conflict = tuple(
        sorted(
            by_state[
                "CONFLICT"
            ]
        )
    )

    unknown = tuple(
        sorted(
            by_state[
                "UNKNOWN"
            ]
        )
    )

    state = _category_state_from_roles(
        present_ids=present,
        bullish_ids=bullish,
        bearish_ids=bearish,
        non_directional_ids=non_directional,
        conflict_ids=conflict,
    )

    return CategoryReductionV1(
        market=market,
        category=category,
        state=state,
        expected_analyzer_ids=expected,
        present_analyzer_ids=present,
        missing_analyzer_ids=missing,
        bullish_analyzer_ids=bullish,
        bearish_analyzer_ids=bearish,
        non_directional_analyzer_ids=non_directional,
        conflict_analyzer_ids=conflict,
        unknown_analyzer_ids=unknown,
        coverage_complete=(
            not missing
        ),
    )


__all__ = [
    "ANALYZER_REDUCTION_SCHEMA_V1",
    "CATEGORY_REDUCTION_SCHEMA_V1",
    "ANALYZER_REDUCER_STATES",
    "CATEGORY_REDUCER_STATES",
    "AnalyzerReductionV1",
    "CategoryReductionV1",
    "expected_category_analyzer_ids_v1",
    "reduce_analyzer_result_v1",
    "reduce_category_v1",
]