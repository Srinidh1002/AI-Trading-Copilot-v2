"""End-to-end PAPER lifecycle runtime for one monitoring cycle."""
from __future__ import annotations

from datetime import datetime

from services.contracts.paper_lifecycle_runtime_result_v1 import (
    PaperLifecycleRuntimeResultV1,
)
from services.contracts.paper_monitoring_lifecycle_v1 import (
    PaperMonitoringEvidenceV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)
from services.paper_trading.paper_hold_transition_applier import (
    apply_hold_transition,
)
from services.paper_trading.paper_monitoring_state_machine import (
    evaluate_paper_position_lifecycle,
)
from services.paper_trading.paper_position_recovery import (
    recover_active_paper_position,
)
from services.paper_trading.paper_stop_protection import (
    apply_move_stop_transition,
)
from services.paper_trading.paper_target_transition_applier import (
    apply_target_transition,
)
from services.paper_trading.paper_terminal_exit_applier import (
    apply_terminal_exit_transition,
)
from services.paper_trading.paper_trade_finalizer import (
    JsonPaperTradeJournalRepository,
    finalize_closed_paper_trade,
)


def run_paper_lifecycle_cycle(
    *,
    runtime_result_id: str,
    runtime_cycle_id: str,
    recovery_result_id: str,
    transition_id: str,
    evaluated_at: datetime,
    evidence: PaperMonitoringEvidenceV1,
    position_repository: JsonPaperPositionRepository,
    journal_repository: JsonPaperTradeJournalRepository,
    maximum_position_age_seconds: float | None = None,
    caution_confidence_threshold: float = 0.55,
    closure_id: str | None = None,
    journal_entry_id: str | None = None,
    finalization_result_id: str | None = None,
) -> PaperLifecycleRuntimeResultV1:
    recovery = recover_active_paper_position(
        recovery_result_id=recovery_result_id,
        recovery_cycle_id=runtime_cycle_id,
        evaluated_at=evaluated_at,
        repository=position_repository,
        maximum_position_age_seconds=maximum_position_age_seconds,
    )

    if recovery.status == "NO_ACTIVE_POSITION":
        return PaperLifecycleRuntimeResultV1(
            runtime_result_id=runtime_result_id,
            runtime_cycle_id=runtime_cycle_id,
            evaluated_at=evaluated_at,
            status="NO_ACTIVE_POSITION",
            recovery_result=recovery,
            transition=None,
            position_before=None,
            position_after=None,
            finalization_result=None,
        )

    if recovery.status != "RECOVERED":
        return PaperLifecycleRuntimeResultV1(
            runtime_result_id=runtime_result_id,
            runtime_cycle_id=runtime_cycle_id,
            evaluated_at=evaluated_at,
            status="BLOCKED",
            recovery_result=recovery,
            transition=None,
            position_before=None,
            position_after=None,
            finalization_result=None,
        )

    position = recovery.recovered_position
    if evidence.position_id != position.position_id:
        raise ValueError("recovered position/evidence mismatch")

    transition = evaluate_paper_position_lifecycle(
        transition_id=transition_id,
        position=position,
        evidence=evidence,
        caution_confidence_threshold=caution_confidence_threshold,
    )

    if transition.action in {"HOLD", "HOLD_WITH_CAUTION"}:
        updated = apply_hold_transition(
            position=position,
            transition=transition,
            repository=position_repository,
        )
    elif transition.action in {"TARGET_1_HIT", "TARGET_2_HIT", "TARGET_3_HIT"}:
        updated = apply_target_transition(
            position=position,
            transition=transition,
            repository=position_repository,
        )
    elif transition.action == "MOVE_STOP":
        updated = apply_move_stop_transition(
            position=position,
            transition=transition,
            repository=position_repository,
        )
    elif transition.action in {"STOP_HIT", "EXIT_NOW"}:
        updated = apply_terminal_exit_transition(
            position=position,
            transition=transition,
            exit_price=evidence.current_bid,
            repository=position_repository,
        )
    elif transition.action == "TRADE_CLOSED":
        updated = position
    else:
        raise ValueError("unsupported lifecycle action")

    finalization = None
    if updated.lifecycle_state == "CLOSED":
        required = {
            "closure_id": closure_id,
            "journal_entry_id": journal_entry_id,
            "finalization_result_id": finalization_result_id,
        }
        missing = tuple(name for name, value in required.items() if not value)
        if missing:
            raise ValueError("terminal lifecycle requires finalization identifiers")

        if transition.action == "TARGET_3_HIT":
            closure_reason = "TARGET_3"
        elif transition.action == "STOP_HIT":
            closure_reason = "STOP"
        elif transition.action == "EXIT_NOW":
            closure_reason = "EARLY_SAFETY_EXIT"
        else:
            closure_reason = "MANUAL_CERTIFIED_CLOSE"

        finalization = finalize_closed_paper_trade(
            finalization_result_id=finalization_result_id,
            closure_id=closure_id,
            journal_entry_id=journal_entry_id,
            finalized_at=evaluated_at,
            closure_reason=closure_reason,
            final_exit_price=evidence.current_bid,
            position=updated,
            journal_repository=journal_repository,
        )

    return PaperLifecycleRuntimeResultV1(
        runtime_result_id=runtime_result_id,
        runtime_cycle_id=runtime_cycle_id,
        evaluated_at=evaluated_at,
        status="APPLIED",
        recovery_result=recovery,
        transition=transition,
        position_before=position,
        position_after=updated,
        finalization_result=finalization,
    )
