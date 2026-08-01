"""Apply non-exit PAPER monitoring transitions to persistent positions."""
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


def apply_hold_transition(
    *,
    position: ActivePaperPositionV1,
    transition: PaperLifecycleTransitionV1,
    repository: JsonPaperPositionRepository,
) -> ActivePaperPositionV1:
    if type(position) is not ActivePaperPositionV1:
        raise TypeError("position")
    if type(transition) is not PaperLifecycleTransitionV1:
        raise TypeError("transition")
    if type(repository) is not JsonPaperPositionRepository:
        raise TypeError("repository")

    if transition.position_id != position.position_id:
        raise ValueError("position/transition mismatch")
    if transition.action not in {"HOLD", "HOLD_WITH_CAUTION"}:
        raise ValueError("unsupported hold transition")
    if transition.previous_state != position.lifecycle_state:
        raise ValueError("previous_state mismatch")
    if transition.next_state != position.lifecycle_state:
        raise ValueError("hold transition cannot change lifecycle state")
    if transition.exit_quantity != 0:
        raise ValueError("hold transition cannot exit quantity")
    if transition.remaining_quantity != position.remaining_quantity:
        raise ValueError("remaining_quantity mismatch")
    if transition.evaluated_at < position.updated_at:
        raise ValueError("transition precedes position")

    event_id = transition.transition_id
    if event_id in position.processed_event_ids:
        return position

    warnings = list(position.warnings)
    if transition.action == "HOLD_WITH_CAUTION":
        warnings.append("HOLD_WITH_CAUTION")
    warnings.extend(transition.warnings)

    updated = replace(
        position,
        updated_at=transition.evaluated_at,
        processed_event_ids=tuple(
            dict.fromkeys(
                (*position.processed_event_ids, event_id)
            )
        ),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    repository.save(updated)
    return updated
