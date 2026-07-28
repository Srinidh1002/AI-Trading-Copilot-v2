"""Opt-in diagnostic comparisons between legacy and canonical results.

This module only adapts supplied mappings and runs the side-effect-free
canonical pipeline. It never invokes a legacy runtime, provider, paper, or
execution boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from services.contracts.runtime_adapters import (
    build_dashboard_decision_v1,
    build_dashboard_snapshot_v1,
    build_live_option_decision_v1,
    build_live_option_snapshot_v1,
)

from .analysis_pipeline import CanonicalAnalysisPipeline
from .comparison_models import CanonicalLegacyComparison, ComparisonDifference
from .decision_pipeline import CanonicalDecisionPipeline
from .pipeline import CanonicalPipelineDependencies


def compare_dashboard_legacy_to_canonical(
    legacy_snapshot: Mapping[str, Any],
    legacy_decision: Mapping[str, Any],
    *,
    canonical_dependencies: CanonicalPipelineDependencies | None = None,
    reference_time: datetime | str | None = None,
) -> CanonicalLegacyComparison:
    """Compare supplied dashboard payloads without calling dashboard code."""
    return _compare(
        source="dashboard",
        snapshot_factory=lambda: build_dashboard_snapshot_v1(
            dict(legacy_snapshot), reference_time=reference_time
        ),
        legacy_factory=lambda snapshot: build_dashboard_decision_v1(
            dict(legacy_decision), snapshot, reference_time=reference_time
        ),
        canonical_dependencies=canonical_dependencies,
    )


def compare_live_option_legacy_to_canonical(
    legacy_decision: Mapping[str, Any],
    *,
    symbol: str,
    exchange: str,
    market_timestamp: datetime | str,
    ltp: float | None,
    timeframes: Mapping[str, Any] | None = None,
    canonical_dependencies: CanonicalPipelineDependencies | None = None,
    reference_time: datetime | str | None = None,
    **identity: Any,
) -> CanonicalLegacyComparison:
    """Compare a supplied live-option result without constructing its pipeline."""
    return _compare(
        source="live_option",
        snapshot_factory=lambda: build_live_option_snapshot_v1(
            symbol=symbol,
            exchange=exchange,
            market_timestamp=market_timestamp,
            ltp=ltp,
            timeframes=timeframes,
            reference_time=reference_time,
            **identity,
        ),
        legacy_factory=lambda snapshot: build_live_option_decision_v1(
            dict(legacy_decision), snapshot, reference_time=reference_time
        ),
        canonical_dependencies=canonical_dependencies,
    )


def _compare(
    *,
    source: str,
    snapshot_factory: Any,
    legacy_factory: Any,
    canonical_dependencies: CanonicalPipelineDependencies | None,
) -> CanonicalLegacyComparison:
    """Contain adaptation/pipeline errors as diagnostics rather than raising."""
    warnings: list[str] = []
    errors: list[str] = []
    snapshot = legacy = analysis = canonical = None
    try:
        snapshot = snapshot_factory()
        warnings.extend(snapshot.warnings)
    except Exception as exc:
        errors.append(f"{source} snapshot adaptation failed: {type(exc).__name__}.")

    if snapshot is not None:
        try:
            legacy = legacy_factory(snapshot)
            warnings.extend(legacy.warnings)
        except Exception as exc:
            errors.append(f"{source} decision adaptation failed: {type(exc).__name__}.")
        try:
            dependencies = canonical_dependencies or CanonicalPipelineDependencies()
            analysis = CanonicalAnalysisPipeline(dependencies.analysis).analyse(snapshot)
            canonical = CanonicalDecisionPipeline().decide(snapshot, analysis)
        except Exception as exc:
            errors.append(f"{source} canonical pipeline failed: {type(exc).__name__}.")

    differences = (
        _differences(legacy, canonical)
        if legacy is not None and canonical is not None else ()
    )
    if canonical is not None:
        warnings.extend(canonical.warnings)
    return CanonicalLegacyComparison(
        source=source,
        snapshot=snapshot,
        legacy_decision=legacy,
        canonical_analysis=analysis,
        canonical_decision=canonical,
        differences=differences,
        warnings=tuple(dict.fromkeys(warnings)),
        errors=tuple(dict.fromkeys(errors)),
        trace_metadata={"comparison": "canonical_legacy.v1", "diagnostic_only": True},
    )


def _differences(legacy: Any, canonical: Any) -> tuple[ComparisonDifference, ...]:
    comparisons = (
        ("action", legacy.action, canonical.action, "HIGH"),
        ("direction", legacy.direction, canonical.direction, "MEDIUM"),
        ("market_regime", legacy.market_regime, canonical.market_regime, "MEDIUM"),
        ("authorization_status", legacy.authorization_status, canonical.authorization_status, "HIGH"),
        ("execution_status", legacy.execution_status, canonical.execution_status, "HIGH"),
        ("confidence", legacy.confidence, canonical.confidence, "INFO"),
        ("technical_score", legacy.technical_score, canonical.technical_score, "INFO"),
        ("options_score", legacy.options_score, canonical.options_score, "INFO"),
        ("institutional_score", legacy.institutional_score, canonical.institutional_score, "INFO"),
        ("data_quality_score", legacy.data_quality_score, canonical.data_quality_score, "INFO"),
        ("data_health_status", legacy.data_health.overall_status, canonical.data_health.overall_status, "HIGH"),
    )
    differences = [
        ComparisonDifference(
            category=category,
            legacy_value=legacy_value,
            canonical_value=canonical_value,
            severity=severity,
            message=f"Legacy and canonical {category.replace('_', ' ')} differ.",
        )
        for category, legacy_value, canonical_value, severity in comparisons
        if legacy_value != canonical_value
    ]
    if bool(legacy.trade_plan) != bool(canonical.trade_plan):
        differences.append(
            ComparisonDifference(
                category="trade_plan_presence",
                legacy_value=bool(legacy.trade_plan),
                canonical_value=bool(canonical.trade_plan),
                severity="INFO",
                message=(
                    "Canonical P2-5 remains analysis-only; this is not an "
                    "execution recommendation."
                ),
            )
        )
    if legacy.blocking_reasons != canonical.blocking_reasons:
        differences.append(
            ComparisonDifference(
                category="blocking_reasons",
                legacy_value=list(legacy.blocking_reasons),
                canonical_value=list(canonical.blocking_reasons),
                severity="MEDIUM",
                message="Legacy and canonical blocking reason sets differ.",
            )
        )
    return tuple(differences)
