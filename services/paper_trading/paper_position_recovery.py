"""Deterministic active PAPER position discovery and restart recovery."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.contracts.paper_position_recovery_result_v1 import (
    PaperPositionRecoveryResultV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)


def recover_active_paper_position(
    *,
    recovery_result_id: str,
    recovery_cycle_id: str,
    evaluated_at: datetime,
    repository: JsonPaperPositionRepository,
    maximum_position_age_seconds: float | None = None,
) -> PaperPositionRecoveryResultV1:
    if type(repository) is not JsonPaperPositionRepository:
        raise TypeError("repository")
    if (
        not isinstance(evaluated_at, datetime)
        or evaluated_at.tzinfo is None
        or evaluated_at.utcoffset() is None
    ):
        raise ValueError("evaluated_at")
    if maximum_position_age_seconds is not None:
        if (
            type(maximum_position_age_seconds) not in (int, float)
            or isinstance(maximum_position_age_seconds, bool)
            or maximum_position_age_seconds < 0.0
        ):
            raise ValueError("maximum_position_age_seconds")

    try:
        active_positions = repository.list_active()
    except ValueError:
        return PaperPositionRecoveryResultV1(
            recovery_result_id=recovery_result_id,
            recovery_cycle_id=recovery_cycle_id,
            evaluated_at=evaluated_at,
            status="BLOCKED",
            discovered_position_count=0,
            recovered_position=None,
            blockers=("POSITION_REPOSITORY_UNREADABLE",),
        )

    count = len(active_positions)
    if count == 0:
        return PaperPositionRecoveryResultV1(
            recovery_result_id=recovery_result_id,
            recovery_cycle_id=recovery_cycle_id,
            evaluated_at=evaluated_at,
            status="NO_ACTIVE_POSITION",
            discovered_position_count=0,
            recovered_position=None,
        )

    if count > 1:
        return PaperPositionRecoveryResultV1(
            recovery_result_id=recovery_result_id,
            recovery_cycle_id=recovery_cycle_id,
            evaluated_at=evaluated_at,
            status="BLOCKED",
            discovered_position_count=count,
            recovered_position=None,
            blockers=("MULTIPLE_ACTIVE_POSITIONS",),
        )

    position = active_positions[0]
    blockers: list[str] = []
    warnings: list[str] = []

    if position.updated_at > evaluated_at:
        blockers.append("POSITION_TIMESTAMP_IN_FUTURE")

    if maximum_position_age_seconds is not None:
        age_seconds = (
            evaluated_at - position.updated_at
        ).total_seconds()
        if age_seconds > maximum_position_age_seconds:
            blockers.append("RECOVERED_POSITION_STALE")

    if position.lifecycle_state not in {
        "OPEN",
        "PARTIALLY_EXITED",
    }:
        blockers.append("POSITION_NOT_ACTIVE")

    if position.remaining_quantity <= 0:
        blockers.append("NO_REMAINING_QUANTITY")

    if position.target_3_hit:
        blockers.append("TERMINAL_TARGET_ALREADY_RECORDED")

    if position.processed_event_ids:
        warnings.append("RECOVERED_WITH_PROCESSED_EVENTS")

    blockers = tuple(dict.fromkeys(blockers))
    warnings = tuple(dict.fromkeys(warnings))

    if blockers:
        return PaperPositionRecoveryResultV1(
            recovery_result_id=recovery_result_id,
            recovery_cycle_id=recovery_cycle_id,
            evaluated_at=evaluated_at,
            status="BLOCKED",
            discovered_position_count=1,
            recovered_position=None,
            blockers=blockers,
            warnings=warnings,
        )

    return PaperPositionRecoveryResultV1(
        recovery_result_id=recovery_result_id,
        recovery_cycle_id=recovery_cycle_id,
        evaluated_at=evaluated_at,
        status="RECOVERED",
        discovered_position_count=1,
        recovered_position=position,
        warnings=warnings,
    )
