"""Side-effect-free dashboard analysis selection and presentation adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
from typing import Any

from services.canonical import (
    CanonicalLegacyComparison,
    CanonicalPipelineDependencies,
    compare_dashboard_legacy_to_canonical,
    run_canonical_analysis,
)
from services.canonical.decision_pipeline import CanonicalDecisionPipeline
from services.contracts.final_decision_v1 import Action, FinalDecisionV1
from services.contracts.market_snapshot_v1 import MarketSnapshotV1
from services.contracts.runtime_adapters import build_dashboard_snapshot_v1


LegacyAnalyzer = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class DashboardAnalysisMode(str, Enum):
    CANONICAL = "canonical"
    LEGACY = "legacy"
    COMPARE = "compare"


def configured_dashboard_analysis_mode(
    value: str | None = None,
) -> DashboardAnalysisMode:
    """Read the temporary non-secret migration setting with a safe default."""
    raw = (
        value
        if value is not None
        else os.getenv(
            "DASHBOARD_ANALYSIS_MODE",
            DashboardAnalysisMode.CANONICAL.value,
        )
    )

    try:
        return DashboardAnalysisMode(str(raw).strip().lower())
    except ValueError:
        return DashboardAnalysisMode.CANONICAL


def _load_legacy_analyzer() -> LegacyAnalyzer:
    """Import the legacy decision engine only when explicitly requested.

    Canonical dashboard imports must not load the legacy trade-engine graph.
    """
    from services.trade.trade_engine import analyze_trade

    return analyze_trade


@dataclass(slots=True)
class DashboardAnalysisResult:
    snapshot: MarketSnapshotV1 | None
    decision: FinalDecisionV1 | None
    legacy_snapshot: Mapping[str, Any] | None = None
    legacy_decision: Mapping[str, Any] | None = None
    comparison: CanonicalLegacyComparison | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    mode: str = DashboardAnalysisMode.CANONICAL.value


@dataclass(slots=True)
class DashboardAnalysisService:
    """Select dashboard analysis mode without acquiring market data."""

    canonical_dependencies: CanonicalPipelineDependencies | None = None
    legacy_analyzer: LegacyAnalyzer | None = None

    def analyse(
        self,
        legacy_snapshot: Mapping[str, Any],
        *,
        mode: DashboardAnalysisMode | str | None = None,
        reference_time: datetime | str | None = None,
    ) -> DashboardAnalysisResult:
        selected_mode = configured_dashboard_analysis_mode(
            mode.value if isinstance(mode, DashboardAnalysisMode) else mode
        )

        if not isinstance(legacy_snapshot, Mapping):
            return DashboardAnalysisResult(
                snapshot=None,
                decision=None,
                errors=("Dashboard snapshot must be a mapping.",),
                mode=selected_mode.value,
            )

        if selected_mode is DashboardAnalysisMode.LEGACY:
            return self._legacy(legacy_snapshot, selected_mode)

        if selected_mode is DashboardAnalysisMode.COMPARE:
            return self._compare(
                legacy_snapshot,
                selected_mode,
                reference_time,
            )

        return self._canonical(
            legacy_snapshot,
            selected_mode,
            reference_time,
        )

    def _get_legacy_analyzer(self) -> LegacyAnalyzer:
        """Return an injected legacy analyzer or lazily load the real one."""
        if self.legacy_analyzer is not None:
            return self.legacy_analyzer

        return _load_legacy_analyzer()

    def _canonical(
        self,
        legacy_snapshot: Mapping[str, Any],
        mode: DashboardAnalysisMode,
        reference_time: datetime | str | None,
    ) -> DashboardAnalysisResult:
        try:
            snapshot = build_dashboard_snapshot_v1(
                legacy_snapshot,
                reference_time=reference_time,
            )

            analysis = run_canonical_analysis(
                snapshot,
                dependencies=self.canonical_dependencies,
            )

            decision = CanonicalDecisionPipeline().decide(
                snapshot,
                analysis,
            )

            warnings = tuple(
                dict.fromkeys(
                    tuple(snapshot.warnings)
                    + tuple(analysis.warnings)
                )
            )

            return DashboardAnalysisResult(
                snapshot=snapshot,
                decision=decision,
                legacy_snapshot=legacy_snapshot,
                warnings=warnings,
                mode=mode.value,
            )

        except Exception as exc:
            return DashboardAnalysisResult(
                snapshot=None,
                decision=None,
                legacy_snapshot=legacy_snapshot,
                errors=(
                    "Canonical dashboard analysis failed: "
                    f"{type(exc).__name__}.",
                ),
                mode=mode.value,
            )

    def _legacy(
        self,
        legacy_snapshot: Mapping[str, Any],
        mode: DashboardAnalysisMode,
    ) -> DashboardAnalysisResult:
        try:
            analyzer = self._get_legacy_analyzer()
            legacy_decision = analyzer(legacy_snapshot)

            return DashboardAnalysisResult(
                snapshot=None,
                decision=None,
                legacy_snapshot=legacy_snapshot,
                legacy_decision=legacy_decision,
                mode=mode.value,
            )

        except Exception as exc:
            return DashboardAnalysisResult(
                snapshot=None,
                decision=None,
                legacy_snapshot=legacy_snapshot,
                errors=(
                    "Legacy dashboard analysis failed: "
                    f"{type(exc).__name__}.",
                ),
                mode=mode.value,
            )

    def _compare(
        self,
        legacy_snapshot: Mapping[str, Any],
        mode: DashboardAnalysisMode,
        reference_time: datetime | str | None,
    ) -> DashboardAnalysisResult:
        # Canonical output remains official in compare mode.
        canonical_result = self._canonical(
            legacy_snapshot,
            mode,
            reference_time,
        )

        if canonical_result.decision is None:
            return canonical_result

        try:
            analyzer = self._get_legacy_analyzer()
            legacy_decision = analyzer(legacy_snapshot)

        except Exception as exc:
            return DashboardAnalysisResult(
                snapshot=canonical_result.snapshot,
                decision=canonical_result.decision,
                legacy_snapshot=legacy_snapshot,
                legacy_decision=None,
                comparison=None,
                warnings=canonical_result.warnings
                + (
                    "Canonical result retained because legacy comparison "
                    "analysis failed.",
                ),
                errors=canonical_result.errors
                + (
                    "Legacy dashboard comparison failed: "
                    f"{type(exc).__name__}.",
                ),
                mode=mode.value,
            )

        try:
            comparison = compare_dashboard_legacy_to_canonical(
                legacy_snapshot,
                legacy_decision,
                canonical_dependencies=self.canonical_dependencies,
                reference_time=reference_time,
            )

            return DashboardAnalysisResult(
                snapshot=comparison.snapshot or canonical_result.snapshot,
                decision=(
                    comparison.canonical_decision
                    or canonical_result.decision
                ),
                legacy_snapshot=legacy_snapshot,
                legacy_decision=legacy_decision,
                comparison=comparison,
                warnings=tuple(
                    dict.fromkeys(
                        canonical_result.warnings
                        + tuple(comparison.warnings)
                    )
                ),
                errors=tuple(
                    dict.fromkeys(
                        canonical_result.errors
                        + tuple(comparison.errors)
                    )
                ),
                mode=mode.value,
            )

        except Exception as exc:
            return DashboardAnalysisResult(
                snapshot=canonical_result.snapshot,
                decision=canonical_result.decision,
                legacy_snapshot=legacy_snapshot,
                legacy_decision=legacy_decision,
                comparison=None,
                warnings=canonical_result.warnings
                + (
                    "Canonical result retained because diagnostic comparison "
                    "failed.",
                ),
                errors=canonical_result.errors
                + (
                    "Dashboard comparison failed: "
                    f"{type(exc).__name__}.",
                ),
                mode=mode.value,
            )


def dashboard_trade_presentation(
    result: DashboardAnalysisResult,
) -> Mapping[str, Any] | None:
    """Map official output to the existing dashboard display vocabulary.

    This function formats contract output only. It does not calculate a
    decision, risk plan, or execution authorization.
    """
    if result.mode == DashboardAnalysisMode.LEGACY.value:
        return result.legacy_decision

    decision = result.decision
    if decision is None:
        return None

    direction = decision.direction.upper()
    technical_score = (
        decision.technical_score
        if decision.technical_score is not None
        else 0.0
    )

    display_decision = {
        Action.BUY.value: "BUY CE",
        Action.SELL.value: "BUY PE",
    }.get(
        decision.action,
        Action.WAIT.value,
    )

    pattern = "Canonical analysis"

    if (
        result.comparison is not None
        and result.comparison.canonical_analysis is not None
    ):
        patterns = (
            result.comparison.canonical_analysis
            .candlestick
            .metadata
            .get("patterns", ())
        )

        if patterns:
            pattern = ", ".join(str(item) for item in patterns)

    reasons = (
        decision.blocking_reasons
        or decision.supporting_reasons
    )

    confidence = (
        decision.confidence
        if decision.confidence is not None
        else 0.0
    )

    institutional_score = (
        decision.institutional_score
        if decision.institutional_score is not None
        else 0.0
    )

    return {
        "decision": display_decision,
        "confidence": confidence,
        "institutional_score": institutional_score,
        "trade_grade": decision.authorization_status,
        "trade_action": decision.execution_status,
        "bull_score": (
            technical_score
            if direction == "BULLISH"
            else 0.0
        ),
        "bear_score": (
            technical_score
            if direction == "BEARISH"
            else 0.0
        ),
        "neutral_score": (
            100.0
            if decision.action == Action.WAIT.value
            else 0.0
        ),
        "trend": {
            "momentum": direction.title(),
            "strength": decision.trend_strength or "Unknown",
            "score": confidence,
        },
        "pattern": {
            "pattern": pattern,
            "signal": decision.action,
        },
        "support_resistance": {
            "Support": None,
            "Resistance": None,
            "OptionSupport": None,
            "OptionResistance": None,
        },
        "entry": None,
        "stop_loss": None,
        "target1": None,
        "target2": None,
        "target3": None,
        "risk": {
            "TARGET3": None,
            "RR": None,
        },
        "risk_level": decision.risk.risk_level,
        "trade_quality": "ANALYSIS_ONLY",
        "reason": (
            " | ".join(reasons)
            or "Canonical analysis completed."
        ),
    }