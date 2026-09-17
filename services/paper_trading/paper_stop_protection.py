"""Deterministic PAPER protected-stop policy and persistence."""
from __future__ import annotations

from dataclasses import replace

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.contracts.paper_monitoring_lifecycle_v1 import (
    PaperLifecycleTransitionV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)


def build_move_stop_transition(
    *,
    transition_id: str,
    evidence_id: str,
    evaluated_at,
    position: ActivePaperPositionV1,
) -> PaperLifecycleTransitionV1:
    """Build one monotonic protected-stop transition from target state."""

    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if position.lifecycle_state == "CLOSED":
        raise ValueError("closed position cannot move stop")
    if evaluated_at < position.updated_at:
        raise ValueError("evaluated_at precedes position")

    proposed_stop = position.current_stop_loss
    reasons: tuple[str, ...]

    if position.target_2_hit:
        proposed_stop = max(
            position.current_stop_loss,
            position.target_1,
        )
        reasons = ("PROTECT_AFTER_TARGET_2",)
    elif position.target_1_hit:
        proposed_stop = max(
            position.current_stop_loss,
            position.entry_price,
        )
        reasons = ("MOVE_TO_BREAKEVEN_AFTER_TARGET_1",)
    else:
        raise ValueError("no target milestone permits stop movement")

    if proposed_stop <= position.current_stop_loss:
        raise ValueError("stop already protected")

    return PaperLifecycleTransitionV1(
        transition_id=transition_id,
        position_id=position.position_id,
        evidence_id=evidence_id,
        evaluated_at=evaluated_at,
        action="MOVE_STOP",
        previous_state=position.lifecycle_state,
        next_state=position.lifecycle_state,
        exit_quantity=0,
        remaining_quantity=position.remaining_quantity,
        effective_stop_loss=proposed_stop,
        reasons=reasons,
    )


def apply_move_stop_transition(
    *,
    position: ActivePaperPositionV1,
    transition: PaperLifecycleTransitionV1,
    repository: JsonPaperPositionRepository,
) -> ActivePaperPositionV1:
    """Persist one idempotent monotonic PAPER stop movement."""

    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(transition) is not PaperLifecycleTransitionV1:
        raise TypeError("transition")
    if type(repository) is not JsonPaperPositionRepository:
        raise TypeError("repository")

    if transition.position_id != position.position_id:
        raise ValueError("position/transition mismatch")
    if transition.action != "MOVE_STOP":
        raise ValueError("unsupported stop transition")

    if transition.transition_id in position.processed_event_ids:
        return position

    if transition.previous_state != position.lifecycle_state:
        raise ValueError("previous_state mismatch")
    if transition.next_state != position.lifecycle_state:
        raise ValueError("MOVE_STOP cannot change lifecycle state")
    if transition.evaluated_at < position.updated_at:
        raise ValueError("transition precedes position")
    if transition.exit_quantity != 0:
        raise ValueError("MOVE_STOP cannot exit quantity")
    if transition.remaining_quantity != position.remaining_quantity:
        raise ValueError("remaining_quantity mismatch")
    if transition.effective_stop_loss <= position.current_stop_loss:
        raise ValueError("stop must move forward")
    if transition.effective_stop_loss > position.target_2:
        raise ValueError("stop exceeds protected policy ceiling")

    if position.target_2_hit:
        minimum_allowed = position.target_1
    elif position.target_1_hit:
        minimum_allowed = position.entry_price
    else:
        raise ValueError("no target milestone permits stop movement")

    if transition.effective_stop_loss < minimum_allowed:
        raise ValueError("stop below protected policy floor")

    updated = replace(
        position,
        updated_at=transition.evaluated_at,
        current_stop_loss=transition.effective_stop_loss,
        processed_event_ids=tuple(
            dict.fromkeys(
                (
                    *position.processed_event_ids,
                    transition.transition_id,
                )
            )
        ),
        warnings=tuple(
            dict.fromkeys(
                (*position.warnings, *transition.warnings)
            )
        ),
    )
    repository.save(updated)
    return updated
