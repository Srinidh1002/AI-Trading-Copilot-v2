"""Apply PAPER stop-hit and early safety-exit transitions."""
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


_EXIT_ACTIONS = {"STOP_HIT", "EXIT_NOW"}


def apply_terminal_exit_transition(
    *,
    position: ActivePaperPositionV1,
    transition: PaperLifecycleTransitionV1,
    exit_price: float,
    repository: JsonPaperPositionRepository,
) -> ActivePaperPositionV1:
    """Persist one idempotent full PAPER stop or safety exit."""

    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(transition) is not PaperLifecycleTransitionV1:
        raise TypeError("transition")
    if type(repository) is not JsonPaperPositionRepository:
        raise TypeError("repository")
    if (
        type(exit_price) not in (int, float)
        or isinstance(exit_price, bool)
        or float(exit_price) <= 0.0
    ):
        raise ValueError("exit_price")

    if transition.position_id != position.position_id:
        raise ValueError("position/transition mismatch")
    if transition.action not in _EXIT_ACTIONS:
        raise ValueError("unsupported terminal exit transition")

    if transition.transition_id in position.processed_event_ids:
        return position

    if position.lifecycle_state == "CLOSED":
        raise ValueError("position already closed")
    if transition.previous_state != position.lifecycle_state:
        raise ValueError("previous_state mismatch")
    if transition.next_state != "CLOSED":
        raise ValueError("terminal exit must close position")
    if transition.evaluated_at < position.updated_at:
        raise ValueError("transition precedes position")
    if transition.exit_quantity != position.remaining_quantity:
        raise ValueError("terminal exit quantity mismatch")
    if transition.remaining_quantity != 0:
        raise ValueError("terminal exit must leave zero quantity")

    realised_increment = (
        float(exit_price) - position.entry_price
    ) * position.remaining_quantity

    warnings = list(position.warnings)
    warnings.extend(transition.warnings)
    warnings.append(
        "STOP_EXIT"
        if transition.action == "STOP_HIT"
        else "EARLY_SAFETY_EXIT"
    )

    updated = replace(
        position,
        updated_at=transition.evaluated_at,
        lifecycle_state="CLOSED",
        remaining_lots=0,
        remaining_quantity=0,
        realized_pnl=position.realized_pnl + realised_increment,
        processed_event_ids=tuple(
            dict.fromkeys(
                (
                    *position.processed_event_ids,
                    transition.transition_id,
                )
            )
        ),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    repository.save(updated)
    return updated
