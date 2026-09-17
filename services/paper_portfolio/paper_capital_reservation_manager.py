"""Pure deterministic P8 capital reservation state machine."""
from __future__ import annotations

import math
from datetime import datetime

from services.contracts.paper_capital_reservation_v1 import (
    PaperCapitalReservationV1,
)
from services.contracts.paper_trade_position_v1 import PaperTradePositionV1


def reserve_pending_paper_capital(
    *,
    reservation_id: str,
    portfolio_id: str,
    admission_request_id: str,
    admission_idempotency_key: str,
    integrated_trade_plan_result_id: str,
    trade_plan_id: str,
    capital_amount: float,
    risk_amount: float,
    initial_quantity: int,
    created_at: datetime,
) -> PaperCapitalReservationV1:
    return PaperCapitalReservationV1(
        reservation_id=reservation_id,
        portfolio_id=portfolio_id,
        admission_request_id=admission_request_id,
        admission_idempotency_key=admission_idempotency_key,
        integrated_trade_plan_result_id=integrated_trade_plan_result_id,
        trade_plan_id=trade_plan_id,
        reservation_status="PENDING_HOLD",
        original_capital_amount=capital_amount,
        remaining_capital_amount=capital_amount,
        released_capital_amount=0.0,
        original_risk_amount=risk_amount,
        remaining_risk_amount=risk_amount,
        initial_quantity=initial_quantity,
        remaining_quantity=initial_quantity,
        created_at=created_at,
        updated_at=created_at,
    )


def activate_paper_capital_reservation(
    *,
    reservation: PaperCapitalReservationV1,
    position: PaperTradePositionV1,
    activated_at: datetime,
    p7_transition_sequence: int,
) -> PaperCapitalReservationV1:
    if type(reservation) is not PaperCapitalReservationV1:
        raise TypeError("reservation must be exact PaperCapitalReservationV1")
    if type(position) is not PaperTradePositionV1:
        raise TypeError("position must be exact PaperTradePositionV1")
    if reservation.reservation_status == "ACTIVE":
        if reservation.position_id == position.position_id:
            return reservation
        raise ValueError("reservation already bound to another position")
    if reservation.reservation_status != "PENDING_HOLD":
        raise ValueError("only PENDING_HOLD can activate")
    if (
        reservation.trade_plan_id != position.trade_plan_id
        or reservation.integrated_trade_plan_result_id
        != position.integrated_trade_plan_result_id
        or reservation.initial_quantity != position.initial_quantity
    ):
        raise ValueError("reservation and position identity mismatch")

    return PaperCapitalReservationV1(
        reservation_id=reservation.reservation_id,
        portfolio_id=reservation.portfolio_id,
        admission_request_id=reservation.admission_request_id,
        admission_idempotency_key=reservation.admission_idempotency_key,
        integrated_trade_plan_result_id=reservation.integrated_trade_plan_result_id,
        trade_plan_id=reservation.trade_plan_id,
        reservation_status="ACTIVE",
        original_capital_amount=reservation.original_capital_amount,
        remaining_capital_amount=reservation.original_capital_amount,
        released_capital_amount=0.0,
        original_risk_amount=reservation.original_risk_amount,
        remaining_risk_amount=reservation.original_risk_amount,
        initial_quantity=reservation.initial_quantity,
        remaining_quantity=position.remaining_quantity,
        created_at=reservation.created_at,
        updated_at=activated_at,
        position_id=position.position_id,
        last_p7_lifecycle_state=position.lifecycle_state,
        last_p7_transition_sequence=p7_transition_sequence,
        processed_fill_ids=tuple(fill.fill_id for fill in position.exit_fills),
        activated_at=activated_at,
        warnings=reservation.warnings,
        metadata=reservation.metadata,
    )


def release_paper_capital_reservation(
    *,
    reservation: PaperCapitalReservationV1,
    position: PaperTradePositionV1,
    updated_at: datetime,
    p7_transition_sequence: int,
) -> PaperCapitalReservationV1:
    if type(reservation) is not PaperCapitalReservationV1:
        raise TypeError("reservation must be exact PaperCapitalReservationV1")
    if type(position) is not PaperTradePositionV1:
        raise TypeError("position must be exact PaperTradePositionV1")
    if reservation.position_id != position.position_id:
        raise ValueError("reservation and position identity mismatch")
    if p7_transition_sequence < reservation.last_p7_transition_sequence:
        raise ValueError("P7 transition regression")

    incoming_fill_ids = tuple(fill.fill_id for fill in position.exit_fills)
    if (
        p7_transition_sequence == reservation.last_p7_transition_sequence
        and set(incoming_fill_ids).issubset(set(reservation.processed_fill_ids))
    ):
        return reservation

    terminal = (
        position.lifecycle_state.startswith("CLOSED_")
        or position.lifecycle_state in {"CANCELLED", "BLOCKED"}
    )
    if terminal:
        remaining_amount = 0.0
        remaining_risk = 0.0
        remaining_quantity = 0
        status = "RELEASED"
        released_at = updated_at
    else:
        if position.lifecycle_state not in {"OPEN", "PARTIALLY_EXITED"}:
            raise ValueError("unsupported active position state")
        if position.remaining_quantity > reservation.remaining_quantity:
            raise ValueError("remaining quantity growth is not allowed")
        ratio = position.remaining_quantity / reservation.initial_quantity
        remaining_amount = reservation.original_capital_amount * ratio
        remaining_risk = reservation.original_risk_amount * ratio
        remaining_quantity = position.remaining_quantity
        status = "ACTIVE"
        released_at = None

    released_amount = reservation.original_capital_amount - remaining_amount
    if released_amount + 1e-9 < reservation.released_capital_amount:
        raise ValueError("released capital cannot decrease")

    return PaperCapitalReservationV1(
        reservation_id=reservation.reservation_id,
        portfolio_id=reservation.portfolio_id,
        admission_request_id=reservation.admission_request_id,
        admission_idempotency_key=reservation.admission_idempotency_key,
        integrated_trade_plan_result_id=reservation.integrated_trade_plan_result_id,
        trade_plan_id=reservation.trade_plan_id,
        reservation_status=status,
        original_capital_amount=reservation.original_capital_amount,
        remaining_capital_amount=remaining_amount,
        released_capital_amount=released_amount,
        original_risk_amount=reservation.original_risk_amount,
        remaining_risk_amount=remaining_risk,
        initial_quantity=reservation.initial_quantity,
        remaining_quantity=remaining_quantity,
        created_at=reservation.created_at,
        updated_at=updated_at,
        position_id=position.position_id,
        last_p7_lifecycle_state=position.lifecycle_state,
        last_p7_transition_sequence=p7_transition_sequence,
        processed_fill_ids=tuple(sorted(set(incoming_fill_ids))),
        activated_at=reservation.activated_at,
        released_at=released_at,
        warnings=reservation.warnings,
        metadata=reservation.metadata,
    )
