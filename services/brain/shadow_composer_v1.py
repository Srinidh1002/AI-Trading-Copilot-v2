"""Pure deterministic composition of a MarketSnapshotV1 into ShadowBrainResultV1."""

from __future__ import annotations

from dataclasses import replace

from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)
from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
    SUPPORTED_MARKETS,
)
from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
)
from services.brain.shadow_brain_v1 import (
    ShadowBrainResultV1,
)
from services.brain.shadow_market_hypothesis_v1 import (
    evaluate_market_hypothesis_v1,
    expected_market_categories_v1,
)
from services.brain.shadow_reducer_v1 import (
    AnalyzerReductionV1,
    reduce_analyzer_result_v1,
    reduce_category_v1,
)


_AUTHORITY_FIELDS = (
    "execution_authority",
    "decision_authority",
    "risk_authority",
    "position_authority",
    "certification_authority",
)


def _require_provenance_text(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty trimmed string."
        )

    return value


def _descriptors_for_market(
    market: str,
) -> dict[str, object]:
    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"Unsupported market: {market!r}."
        )

    descriptors = {
        descriptor.analyzer_id:
            descriptor
        for descriptor
        in DEFAULT_ANALYZER_REGISTRY_V1.descriptors
        if market
        in descriptor.markets
    }

    if not descriptors:
        raise ValueError(
            f"No registered analyzers for market={market!r}."
        )

    return descriptors


def _expected_production_analyzer_ids(
    market: str,
) -> tuple[str, ...]:
    descriptors = (
        _descriptors_for_market(
            market
        )
    )

    expected = tuple(
        sorted(
            analyzer_id
            for analyzer_id, descriptor
            in descriptors.items()
            if descriptor.currently_consumed_by_production
        )
    )

    if not expected:
        raise ValueError(
            f"No production analyzers registered for market={market!r}."
        )

    return expected


def _revalidate_evidence(
    evidence: EvidenceV1,
) -> EvidenceV1:
    if not isinstance(
        evidence,
        EvidenceV1,
    ):
        raise TypeError(
            "Snapshot analyzer evidence must contain EvidenceV1 values."
        )

    return replace(
        evidence
    )


def _revalidate_analyzer_result(
    result: AnalyzerResultV1,
) -> AnalyzerResultV1:
    if not isinstance(
        result,
        AnalyzerResultV1,
    ):
        raise TypeError(
            "Snapshot analyzer_results must contain AnalyzerResultV1 values."
        )

    evidence = tuple(
        _revalidate_evidence(
            item
        )
        for item
        in result.evidence
    )

    return replace(
        result,
        evidence=evidence,
    )


def _validate_global_evidence_ids(
    results: tuple[
        AnalyzerResultV1,
        ...,
    ],
) -> None:
    evidence_ids = tuple(
        evidence.evidence_id
        for result
        in results
        for evidence
        in result.evidence
    )

    if len(
        evidence_ids
    ) != len(
        set(
            evidence_ids
        )
    ):
        raise ValueError(
            "Evidence IDs must be globally unique across the entire snapshot."
        )


def _revalidate_snapshot(
    snapshot: MarketSnapshotV1,
) -> MarketSnapshotV1:
    if not isinstance(
        snapshot,
        MarketSnapshotV1,
    ):
        raise TypeError(
            "snapshot must be MarketSnapshotV1."
        )

    input_snapshot_sha256 = (
        snapshot.snapshot_sha256
    )

    analyzer_results = tuple(
        _revalidate_analyzer_result(
            result
        )
        for result
        in snapshot.analyzer_results
    )

    validated = replace(
        snapshot,
        analyzer_results=analyzer_results,
    )

    if (
        validated.registry_schema_version
        != DEFAULT_ANALYZER_REGISTRY_V1.schema_version
    ):
        raise ValueError(
            "Snapshot registry_schema_version does not match "
            "the frozen analyzer registry."
        )

    expected_production = (
        _expected_production_analyzer_ids(
            validated.market
        )
    )

    if (
        validated.expected_production_analyzers
        != expected_production
    ):
        raise ValueError(
            "Snapshot expected_production_analyzers must exactly "
            "match the frozen production registry."
        )

    descriptors = (
        _descriptors_for_market(
            validated.market
        )
    )

    analyzer_ids = tuple(
        result.analyzer
        for result
        in validated.analyzer_results
    )

    if len(
        analyzer_ids
    ) != len(
        set(
            analyzer_ids
        )
    ):
        raise ValueError(
            "Snapshot analyzer IDs must be unique."
        )

    for result in validated.analyzer_results:
        descriptor = descriptors.get(
            result.analyzer
        )

        if descriptor is None:
            raise ValueError(
                "Snapshot contains an analyzer not registered "
                f"for market={validated.market!r}: "
                f"{result.analyzer!r}."
            )

        if (
            result.analyzer_version
            != descriptor.analyzer_version
        ):
            raise ValueError(
                "Snapshot analyzer version does not match "
                "the frozen registry descriptor."
            )

        for evidence in result.evidence:
            if (
                evidence.category
                != descriptor.category
            ):
                raise ValueError(
                    "Snapshot evidence category does not match "
                    "the frozen registry descriptor."
                )

    source_strategy_version = (
        _require_provenance_text(
            name="source_strategy_version",
            value=validated.source_strategy_version,
        )
    )

    source_policy_epoch = (
        _require_provenance_text(
            name="source_policy_epoch",
            value=validated.source_policy_epoch,
        )
    )

    source_runtime_ref = (
        _require_provenance_text(
            name="source_runtime_ref",
            value=validated.source_runtime_ref,
        )
    )

    if (
        source_strategy_version
        != validated.source_strategy_version
        or source_policy_epoch
        != validated.source_policy_epoch
        or source_runtime_ref
        != validated.source_runtime_ref
    ):
        raise ValueError(
            "Snapshot provenance values may not be normalized by composer."
        )

    for field_name in _AUTHORITY_FIELDS:
        if getattr(
            validated,
            field_name,
        ) is not False:
            raise ValueError(
                f"{field_name} must remain False for shadow composition."
            )

    _validate_global_evidence_ids(
        validated.analyzer_results
    )

    if (
        validated.snapshot_sha256
        != input_snapshot_sha256
    ):
        raise ValueError(
            "Snapshot changed during contract revalidation."
        )

    return validated


def _production_results(
    snapshot: MarketSnapshotV1,
) -> tuple[
    AnalyzerResultV1,
    ...,
]:
    expected = set(
        snapshot.expected_production_analyzers
    )

    return tuple(
        result
        for result
        in snapshot.analyzer_results
        if result.analyzer
        in expected
    )


def _analyzer_reductions(
    snapshot: MarketSnapshotV1,
) -> tuple[
    AnalyzerReductionV1,
    ...,
]:
    reductions = tuple(
        reduce_analyzer_result_v1(
            result
        )
        for result
        in _production_results(
            snapshot
        )
    )

    return tuple(
        sorted(
            reductions,
            key=lambda item:
                item.analyzer,
        )
    )


def _quality_metadata_ids(
    snapshot: MarketSnapshotV1,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
]:
    unverified = tuple(
        sorted(
            evidence.evidence_id
            for result
            in snapshot.analyzer_results
            for evidence
            in result.evidence
            if evidence.status
            == "UNVERIFIED"
        )
    )

    stale = tuple(
        sorted(
            evidence.evidence_id
            for result
            in snapshot.analyzer_results
            for evidence
            in result.evidence
            if evidence.freshness
            == "STALE"
        )
    )

    return (
        unverified,
        stale,
    )


def compose_shadow_brain_v1(
    snapshot: MarketSnapshotV1,
) -> ShadowBrainResultV1:
    snapshot = _revalidate_snapshot(
        snapshot
    )

    analyzer_reductions = (
        _analyzer_reductions(
            snapshot
        )
    )

    category_reductions = tuple(
        reduce_category_v1(
            market=snapshot.market,
            category=category,
            analyzer_reductions=tuple(
                reduction
                for reduction
                in analyzer_reductions
                if reduction.category
                == category
            ),
        )
        for category
        in expected_market_categories_v1(
            snapshot.market
        )
    )

    hypothesis = (
        evaluate_market_hypothesis_v1(
            market=snapshot.market,
            category_reductions=category_reductions,
            analyzer_reductions=analyzer_reductions,
        )
    )

    (
        unverified_evidence_ids,
        stale_evidence_ids,
    ) = _quality_metadata_ids(
        snapshot
    )

    source_strategy_version = (
        _require_provenance_text(
            name="source_strategy_version",
            value=snapshot.source_strategy_version,
        )
    )

    source_policy_epoch = (
        _require_provenance_text(
            name="source_policy_epoch",
            value=snapshot.source_policy_epoch,
        )
    )

    source_runtime_ref = (
        _require_provenance_text(
            name="source_runtime_ref",
            value=snapshot.source_runtime_ref,
        )
    )

    return ShadowBrainResultV1(
        market=snapshot.market,
        snapshot_sha256=snapshot.snapshot_sha256,
        snapshot_at=snapshot.snapshot_at,
        generated_at=snapshot.generated_at,
        source_strategy_version=source_strategy_version,
        source_policy_epoch=source_policy_epoch,
        source_runtime_ref=source_runtime_ref,
        production_coverage_pct=snapshot.production_coverage_pct,
        production_complete=snapshot.production_complete,
        missing_production_analyzers=(
            snapshot.missing_production_analyzers
        ),
        unverified_evidence_ids=(
            unverified_evidence_ids
        ),
        stale_evidence_ids=(
            stale_evidence_ids
        ),
        hypothesis=hypothesis,
        execution_authority=False,
        decision_authority=False,
        risk_authority=False,
        position_authority=False,
        certification_authority=False,
    )


__all__ = [
    "compose_shadow_brain_v1",
]