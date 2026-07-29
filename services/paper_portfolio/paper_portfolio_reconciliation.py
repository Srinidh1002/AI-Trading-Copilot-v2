"""Pure deterministic P8 portfolio reconciliation validation."""
from __future__ import annotations

import math

from services.contracts.paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)


def validate_paper_portfolio_reconciliation(
    *,
    portfolio_snapshot: PaperPortfolioSnapshotV1,
    paper_trade_snapshots: tuple[PaperTradePersistenceSnapshotV1, ...],
) -> tuple[str, ...]:
    if type(portfolio_snapshot) is not PaperPortfolioSnapshotV1:
        raise TypeError("portfolio_snapshot must be exact PaperPortfolioSnapshotV1")
    if type(paper_trade_snapshots) is not tuple or any(
        type(item) is not PaperTradePersistenceSnapshotV1
        for item in paper_trade_snapshots
    ):
        raise TypeError("paper_trade_snapshots must contain exact P7 snapshots")

    codes: list[str] = []
    p7_positions = {}
    for snapshot in paper_trade_snapshots:
        if snapshot.position is None:
            continue
        position = snapshot.position
        prior = p7_positions.get(position.position_id)
        if prior is not None:
            if prior.to_json() != position.to_json():
                codes.append("DUPLICATE_POSITION_ID")
            continue
        p7_positions[position.position_id] = position

    reservations_by_position = {
        item.position_id: item
        for item in portfolio_snapshot.reservations
        if item.position_id is not None
    }

    for reference in portfolio_snapshot.position_references:
        position = p7_positions.get(reference.position_id)
        if position is None:
            codes.append("UNKNOWN_POSITION")
            continue
        if (
            reference.trade_plan_id != position.trade_plan_id
            or reference.integrated_trade_plan_result_id
            != position.integrated_trade_plan_result_id
        ):
            codes.append("P7_IDENTITY_MISMATCH")
        if reference.remaining_quantity != position.remaining_quantity:
            codes.append("P7_QUANTITY_MISMATCH")
        if reference.lifecycle_state != position.lifecycle_state:
            codes.append("RESERVATION_POSITION_MISMATCH")

        reservation = reservations_by_position.get(reference.position_id)
        if reservation is None:
            codes.append("ACTIVE_RESERVATION_MISSING_POSITION")
            continue
        terminal = (
            position.lifecycle_state.startswith("CLOSED_")
            or position.lifecycle_state in {"CANCELLED", "BLOCKED"}
        )
        if terminal and reservation.reservation_status != "RELEASED":
            codes.append("TERMINAL_RESERVATION_ACTIVE")
        if not terminal and reservation.reservation_status != "ACTIVE":
            codes.append("RESERVATION_POSITION_MISMATCH")

    for reservation in portfolio_snapshot.reservations:
        if reservation.reservation_status == "ACTIVE" and reservation.position_id not in p7_positions:
            codes.append("UNKNOWN_POSITION")

    return tuple(dict.fromkeys(codes))
