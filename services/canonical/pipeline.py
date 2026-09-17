"""Application-facing additive canonical pipeline API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from collections.abc import Callable

from services.contracts.analysis_result_v1 import AnalysisResultV1
from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import MarketSnapshotV1
from services.observability import (
    AuditContext,
    AuditEmitter,
    create_audit_event,
)

from .analysis_pipeline import (
    CanonicalAnalysisDependencies,
    CanonicalAnalysisPipeline,
)
from .decision_pipeline import CanonicalDecisionPipeline


@dataclass(frozen=True, slots=True)
class CanonicalPipelineDependencies:
    """Explicit analysis dependencies for deterministic canonical runs."""

    analysis: CanonicalAnalysisDependencies = field(
        default_factory=CanonicalAnalysisDependencies
    )
    session_validation_enabled: bool = False
    trading_calendar: object | None = None
    session_policy: object | None = None
    session_validation_mode: str = "LENIENT_ANALYSIS"
    session_clock: Callable[[], datetime] | None = None


def run_canonical_analysis(
    snapshot: MarketSnapshotV1,
    *,
    dependencies: CanonicalPipelineDependencies | None = None,
    audit_emitter: AuditEmitter | None = None,
    audit_context: AuditContext | None = None,
) -> AnalysisResultV1:
    """Run canonical analysis without decision or execution side effects."""

    if not isinstance(snapshot, MarketSnapshotV1):
        raise TypeError("snapshot must be a MarketSnapshotV1.")

    resolved_dependencies = dependencies or CanonicalPipelineDependencies()
    emitter = audit_emitter or AuditEmitter()

    emitter.emit(
        create_audit_event(
            "ANALYSIS_STARTED",
            component="canonical",
            operation="analyse",
            outcome="STARTED",
            context=audit_context,
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
        )
    )

    try:
        analysis = CanonicalAnalysisPipeline(
            resolved_dependencies.analysis
        ).analyse(snapshot)
    except Exception:
        emitter.emit(
            create_audit_event(
                "ANALYSIS_FAILED",
                component="canonical",
                operation="analyse",
                outcome="FAILED",
                severity="ERROR",
                context=audit_context,
                snapshot_id=snapshot.snapshot_id,
                symbol=snapshot.symbol,
                exchange=snapshot.exchange,
                errors=("Canonical analysis failed.",),
            )
        )
        raise

    emitter.emit(
        create_audit_event(
            "ANALYSIS_COMPLETED",
            component="canonical",
            operation="analyse",
            outcome=(
                "SUCCEEDED"
                if analysis.analysis_valid
                else "BLOCKED"
            ),
            context=audit_context,
            snapshot_id=snapshot.snapshot_id,
            analysis_id=analysis.analysis_id,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            attributes={
                "validation_passed": analysis.analysis_valid,
                "warning_count": len(analysis.warnings),
                "error_count": len(analysis.engine_errors),
            },
        )
    )

    return analysis


def run_canonical_pipeline(
    snapshot: MarketSnapshotV1,
    *,
    dependencies: CanonicalPipelineDependencies | None = None,
    audit_emitter: AuditEmitter | None = None,
    audit_context: AuditContext | None = None,
) -> FinalDecisionV1:
    """Run canonical analysis and decision without I/O or execution."""

    if not isinstance(snapshot, MarketSnapshotV1):
        raise TypeError("snapshot must be a MarketSnapshotV1.")

    emitter = audit_emitter or AuditEmitter()

    emitter.emit(
        create_audit_event(
            "SNAPSHOT_RECEIVED",
            component="canonical",
            operation="pipeline",
            outcome="STARTED",
            context=audit_context,
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            attributes={
                "validation_passed": snapshot.validation_passed,
            },
        )
    )

    resolved_dependencies = dependencies or CanonicalPipelineDependencies()
    if resolved_dependencies.session_validation_enabled:
        from services.market_session import validate_market_session
        session = validate_market_session(snapshot, calendar=resolved_dependencies.trading_calendar, policy=resolved_dependencies.session_policy, validation_mode=resolved_dependencies.session_validation_mode, clock=resolved_dependencies.session_clock)
        if not session.analysis_allowed:
            analysis = AnalysisResultV1(snapshot_id=snapshot.snapshot_id, symbol=snapshot.symbol, created_at=snapshot.captured_at, market_timestamp=snapshot.market_timestamp, market_session=session.session_state, validation_errors=list(session.blockers), engine_errors={"market_data": tuple(session.blockers)}, trace_metadata={"pipeline": "canonical_analysis.v1", "session_state": session.session_state})
        else:
            analysis = run_canonical_analysis(snapshot, dependencies=resolved_dependencies, audit_emitter=emitter, audit_context=audit_context)
    else:
        analysis = run_canonical_analysis(snapshot, dependencies=resolved_dependencies, audit_emitter=emitter, audit_context=audit_context)

    emitter.emit(
        create_audit_event(
            "DECISION_STARTED",
            component="canonical",
            operation="decide",
            outcome="STARTED",
            context=audit_context,
            snapshot_id=snapshot.snapshot_id,
            analysis_id=analysis.analysis_id,
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
        )
    )

    try:
        decision = CanonicalDecisionPipeline().decide(
            snapshot,
            analysis,
        )
    except Exception:
        emitter.emit(
            create_audit_event(
                "DECISION_FAILED",
                component="canonical",
                operation="decide",
                outcome="FAILED",
                severity="ERROR",
                context=audit_context,
                snapshot_id=snapshot.snapshot_id,
                analysis_id=analysis.analysis_id,
                symbol=snapshot.symbol,
                exchange=snapshot.exchange,
                errors=("Canonical decision failed.",),
            )
        )
        raise

    blocked = decision.authorization_status == "BLOCKED"

    emitter.emit(
        create_audit_event(
            (
                "DECISION_BLOCKED"
                if blocked
                else "DECISION_COMPLETED"
            ),
            component="canonical",
            operation="decide",
            outcome=(
                "BLOCKED"
                if blocked
                else "SUCCEEDED"
            ),
            context=audit_context,
            snapshot_id=snapshot.snapshot_id,
            analysis_id=analysis.analysis_id,
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            exchange=decision.exchange,
            action=decision.action,
            authorization_status=decision.authorization_status,
            execution_status=decision.execution_status,
            attributes={
                "blocker_count": len(
                    decision.blocking_reasons
                ),
                "trade_plan_present": (
                    decision.trade_plan is not None
                ),
            },
        )
    )

    return decision
