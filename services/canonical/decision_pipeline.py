"""Canonical, side-effect-free conversion from analysis to FinalDecision v1."""

from __future__ import annotations

from dataclasses import dataclass
from services.contracts.analysis_result_v1 import AnalysisResultV1, DirectionalBias
from services.contracts.final_decision_v1 import (
    Action,
    AuthorizationStatus,
    DataHealthSummary,
    ExecutionStatus,
    FinalDecisionV1,
    RiskSummary,
)
from services.contracts.market_snapshot_v1 import MarketSnapshotV1


@dataclass(slots=True)
class CanonicalDecisionPipeline:
    """Build an analysis-only decision; execution authorization is out of scope."""

    def decide(self, snapshot: MarketSnapshotV1, analysis: AnalysisResultV1) -> FinalDecisionV1:
        if not isinstance(snapshot, MarketSnapshotV1) or not isinstance(analysis, AnalysisResultV1):
            raise TypeError("snapshot and analysis must use their canonical v1 contracts.")
        blocks = list(snapshot.critical_errors) + list(analysis.validation_errors)
        action = self._action_for(analysis)
        if snapshot.snapshot_id != analysis.snapshot_id:
            blocks.append("Analysis snapshot identity does not match the decision snapshot.")
        if not snapshot.validation_passed:
            blocks.append("Snapshot validation failed.")
        if snapshot.is_stale:
            blocks.append("Snapshot is stale.")
        if not analysis.analysis_valid:
            blocks.append("Canonical analysis is invalid.")
        if analysis.directional_bias == DirectionalBias.CONFLICTED.value:
            blocks.append("Directional evidence is conflicted.")
        authorization = AuthorizationStatus.BLOCKED if blocks else AuthorizationStatus.ANALYSIS_ONLY
        if blocks:
            action = Action.WAIT
        return FinalDecisionV1(
            snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol,
            exchange=snapshot.exchange, instrument_type=snapshot.instrument_type,
            created_at=analysis.created_at,
            market_timestamp=snapshot.market_timestamp,
            expiry=snapshot.expiry, strike=snapshot.strike, option_type=snapshot.option_type,
            action=action, authorization_status=authorization,
            execution_status=ExecutionStatus.NOT_REQUESTED,
            market_regime=analysis.market_regime, direction=analysis.directional_bias,
            trend_strength=(str(analysis.trend_strength) if analysis.trend_strength is not None else None),
            volatility_state=analysis.volatility_state, market_session=analysis.market_session,
            confidence=analysis.technical.confidence,
            trade_quality_score=None, institutional_score=analysis.institutional_score,
            technical_score=analysis.technical_score, options_score=analysis.options_score,
            risk_score=None, data_quality_score=analysis.data_quality_score,
            risk=RiskSummary(risk_status="NOT_EVALUATED"),
            supporting_reasons=analysis.supporting_reasons,
            contradictions=analysis.contradictions,
            blocking_reasons=tuple(dict.fromkeys(blocks)),
            warnings=analysis.warnings,
            options_interpretation=analysis.options.metadata,
            data_health=DataHealthSummary(
                overall_status=getattr(
                    snapshot.overall_status,
                    "value",
                    snapshot.overall_status,
                ),
                validation_passed=snapshot.validation_passed,
                critical_errors=tuple(snapshot.critical_errors),
                warnings=tuple(snapshot.warnings),
                missing_sources=tuple(snapshot.missing_sources),
                stale_sources=tuple(snapshot.stale_sources),
            ),
            source_timestamps=analysis.source_timestamps,
            trace_metadata={"pipeline": "canonical_decision.v1", "analysis_id": analysis.analysis_id},
            internal_errors=tuple(error for errors in analysis.engine_errors.values() for error in errors),
        )

    @staticmethod
    def _action_for(analysis: AnalysisResultV1) -> str:
        if analysis.directional_bias == DirectionalBias.BULLISH.value:
            return Action.BUY.value
        if analysis.directional_bias == DirectionalBias.BEARISH.value:
            return Action.SELL.value
        return Action.WAIT.value
