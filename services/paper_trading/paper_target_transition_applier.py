"""Apply PAPER target transitions to persistent active positions."""
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


_TARGET_ACTIONS = {
    "TARGET_1_HIT": ("target_1", "target_1_hit"),
    "TARGET_2_HIT": ("target_2", "target_2_hit"),
    "TARGET_3_HIT": ("target_3", "target_3_hit"),
}


def apply_target_transition(
    *,
    position: ActivePaperPositionV1,
    transition: PaperLifecycleTransitionV1,
    repository: JsonPaperPositionRepository,
) -> ActivePaperPositionV1:
    """Persist one idempotent T1/T2/T3 PAPER partial or final exit."""

    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(transition) is not PaperLifecycleTransitionV1:
        raise TypeError("transition")
    if type(repository) is not JsonPaperPositionRepository:
        raise TypeError("repository")

    if transition.position_id != position.position_id:
        raise ValueError("position/transition mismatch")
    if transition.action not in _TARGET_ACTIONS:
        raise ValueError("unsupported target transition")

    if transition.transition_id in position.processed_event_ids:
        return position

    if transition.previous_state != position.lifecycle_state:
        raise ValueError("previous_state mismatch")
    if transition.evaluated_at < position.updated_at:
        raise ValueError("transition precedes position")

    if position.lifecycle_state == "CLOSED":
        raise ValueError("closed position cannot process target")
    if transition.exit_quantity <= 0:
        raise ValueError("target exit quantity")
    if transition.exit_quantity > position.remaining_quantity:
        raise ValueError("target exit exceeds remaining quantity")
    if transition.exit_quantity % position.lot_size != 0:
        raise ValueError("target exit must use whole lots")

    expected_remaining = (
        position.remaining_quantity - transition.exit_quantity
    )
    if transition.remaining_quantity != expected_remaining:
        raise ValueError("remaining_quantity mismatch")

    expected_state = (
        "CLOSED"
        if expected_remaining == 0
        else "PARTIALLY_EXITED"
    )
    if transition.next_state != expected_state:
        raise ValueError("next_state mismatch")

    target_field, hit_field = _TARGET_ACTIONS[transition.action]
    if getattr(position, hit_field):
        raise ValueError("target already recorded")

    if transition.action == "TARGET_2_HIT" and not position.target_1_hit:
        raise ValueError("TARGET_2 requires TARGET_1")
    if transition.action == "TARGET_3_HIT" and not position.target_2_hit:
        raise ValueError("TARGET_3 requires TARGET_2")

    exit_price = getattr(position, target_field)
    realised_increment = (
        exit_price - position.entry_price
    ) * transition.exit_quantity

    hit_updates = {
        "target_1_hit": position.target_1_hit,
        "target_2_hit": position.target_2_hit,
        "target_3_hit": position.target_3_hit,
    }
    hit_updates[hit_field] = True

    updated = replace(
        position,
        updated_at=transition.evaluated_at,
        lifecycle_state=expected_state,
        remaining_lots=expected_remaining // position.lot_size,
        remaining_quantity=expected_remaining,
        realized_pnl=position.realized_pnl + realised_increment,
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
        **hit_updates,
    )
    repository.save(updated)
    return updated
