"""Stateful P8 portfolio lifecycle coordination over certified P7 snapshots."""
from __future__ import annotations

import hashlib
from datetime import datetime

from services.contracts.paper_capital_reservation_v1 import PaperCapitalReservationV1
from services.contracts.paper_portfolio_admission_result_v1 import PaperPortfolioAdmissionResultV1
from services.contracts.paper_portfolio_persistence_snapshot_v1 import PaperPortfolioPersistenceSnapshotV1
from services.contracts.paper_portfolio_position_reference_v1 import PaperPortfolioPositionReferenceV1
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1
from services.contracts.paper_trade_position_v1 import PaperTradePositionV1

from .paper_capital_reservation_manager import (
    activate_paper_capital_reservation,
    release_paper_capital_reservation,
)
from .paper_portfolio_aggregation import aggregate_paper_portfolio
from .paper_portfolio_persistence_service import PaperPortfolioPersistenceService


def _replace_reservation(values, replacement):
    found = False
    result = []
    for item in values:
        if item.reservation_id == replacement.reservation_id:
            result.append(replacement)
            found = True
        else:
            result.append(item)
    if not found:
        raise ValueError("reservation not found")
    return tuple(result)


def _replace_reference(values, replacement):
    result = [item for item in values if item.position_id != replacement.position_id]
    result.append(replacement)
    return tuple(result)


def project_paper_portfolio_position(
    *,
    portfolio_id: str,
    reservation: PaperCapitalReservationV1,
    position: PaperTradePositionV1,
    transition_sequence: int,
    updated_at: datetime,
    last_observation_id: str | None,
) -> PaperPortfolioPositionReferenceV1:
    if type(reservation) is not PaperCapitalReservationV1:
        raise TypeError("reservation")
    if type(position) is not PaperTradePositionV1:
        raise TypeError("position")
    if reservation.position_id != position.position_id:
        raise ValueError("reservation and position identity mismatch")

    return PaperPortfolioPositionReferenceV1(
        portfolio_id=portfolio_id,
        reservation_id=reservation.reservation_id,
        position_id=position.position_id,
        trade_plan_id=position.trade_plan_id,
        integrated_trade_plan_result_id=position.integrated_trade_plan_result_id,
        selected_option_contract_id=position.selected_option_contract_id,
        underlying_symbol=position.underlying_symbol,
        exchange=position.exchange or position.market,
        option_symbol=position.option_symbol,
        option_type=position.option_type,
        economic_direction=position.direction,
        expiry=position.expiry,
        lifecycle_state=position.lifecycle_state,
        transition_sequence=transition_sequence,
        initial_lot_count=position.initial_lot_count,
        remaining_lot_count=position.remaining_lot_count,
        lot_size=position.lot_size,
        initial_quantity=position.initial_quantity,
        remaining_quantity=position.remaining_quantity,
        initial_capital_amount=reservation.original_capital_amount,
        remaining_capital_amount=reservation.remaining_capital_amount,
        initial_risk_amount=reservation.original_risk_amount,
        remaining_risk_amount=reservation.remaining_risk_amount,
        realized_net_pnl=position.realized_net_pnl,
        unrealized_pnl=position.unrealized_pnl,
        total_pnl=position.total_pnl,
        exit_fill_ids=tuple(fill.fill_id for fill in position.exit_fills),
        last_observation_id=last_observation_id,
        updated_at=updated_at,
    )


class PaperPortfolioLifecycleCoordinator:
    def __init__(self, persistence_service):
        if type(persistence_service) is not PaperPortfolioPersistenceService:
            raise TypeError("persistence_service")
        self.persistence_service = persistence_service

    def persist_approved_admission(self, result):
        if type(result) is not PaperPortfolioAdmissionResultV1:
            raise TypeError("result")
        if result.status != "APPROVED":
            raise ValueError("only APPROVED admission can be persisted")

        existing = self.persistence_service.get(result.portfolio_id)
        admission_records = {} if existing is None else dict(existing.admission_idempotency_records)
        prior = admission_records.get(result.admission_idempotency_key)
        if prior is not None:
            if prior == result.admission_payload_hash:
                return existing
            raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")

        event_records = {} if existing is None else dict(existing.processed_portfolio_event_hashes)
        event_hash = hashlib.sha256(result.to_json().encode("utf-8")).hexdigest()
        prior_event = event_records.get(result.portfolio_event_id)
        if prior_event is not None and prior_event != event_hash:
            raise ValueError("portfolio event payload conflict")

        admission_records[result.admission_idempotency_key] = result.admission_payload_hash
        event_records[result.portfolio_event_id] = event_hash

        envelope = PaperPortfolioPersistenceSnapshotV1(
            portfolio_id=result.portfolio_id,
            portfolio_snapshot=result.resulting_snapshot,
            admission_idempotency_records=admission_records,
            update_idempotency_records={} if existing is None else dict(existing.update_idempotency_records),
            processed_portfolio_event_hashes=event_records,
            processed_p7_transition_hashes={} if existing is None else dict(existing.processed_p7_transition_hashes),
            processed_p7_fill_hashes={} if existing is None else dict(existing.processed_p7_fill_hashes),
            created_at=result.evaluated_at if existing is None else existing.created_at,
            updated_at=result.evaluated_at,
            event_sequence=result.resulting_snapshot.event_sequence,
        )
        self.persistence_service.save(envelope)
        return envelope

    def apply_p7_snapshot(
        self,
        *,
        portfolio_id: str,
        policy: PaperPortfolioPolicyV1,
        p7_snapshot: PaperTradePersistenceSnapshotV1,
        result_snapshot_id: str,
        portfolio_event_id: str,
        update_idempotency_key: str,
        updated_at: datetime,
    ):
        if type(policy) is not PaperPortfolioPolicyV1:
            raise TypeError("policy")
        if type(p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError("p7_snapshot")
        if p7_snapshot.position is None:
            raise ValueError("P7 snapshot has no position")

        current = self.persistence_service.get(portfolio_id)
        if current is None:
            raise ValueError("portfolio not found")

        payload_hash = p7_snapshot.integrity_hash
        update_records = dict(current.update_idempotency_records)
        prior = update_records.get(update_idempotency_key)
        if prior is not None:
            if prior == payload_hash:
                return current
            raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")

        event_records = dict(current.processed_portfolio_event_hashes)
        prior_event = event_records.get(portfolio_event_id)
        if prior_event is not None:
            if prior_event == payload_hash:
                return current
            raise ValueError("portfolio event payload conflict")

        position = p7_snapshot.position
        matches = [
            item
            for item in current.portfolio_snapshot.reservations
            if item.trade_plan_id == position.trade_plan_id
            and item.integrated_trade_plan_result_id == position.integrated_trade_plan_result_id
        ]
        if len(matches) != 1:
            raise ValueError("matching reservation must be unique")
        reservation = matches[0]
        sequence = p7_snapshot.lifecycle_state.transition_sequence

        if reservation.reservation_status == "PENDING_HOLD":
            if position.lifecycle_state != "OPEN":
                raise ValueError("pending hold can only activate from P7 OPEN")
            next_reservation = activate_paper_capital_reservation(
                reservation=reservation,
                position=position,
                activated_at=updated_at,
                p7_transition_sequence=sequence,
            )
        else:
            next_reservation = release_paper_capital_reservation(
                reservation=reservation,
                position=position,
                updated_at=updated_at,
                p7_transition_sequence=sequence,
            )

        next_reference = project_paper_portfolio_position(
            portfolio_id=portfolio_id,
            reservation=next_reservation,
            position=position,
            transition_sequence=sequence,
            updated_at=updated_at,
            last_observation_id=(
                None
                if p7_snapshot.latest_observation is None
                else p7_snapshot.latest_observation.observation_id
            ),
        )

        next_snapshot = aggregate_paper_portfolio(
            portfolio_snapshot_id=result_snapshot_id,
            portfolio_id=portfolio_id,
            policy=policy,
            trading_day_id=current.portfolio_snapshot.trading_day_id,
            starting_capital=current.portfolio_snapshot.starting_capital,
            reservations=_replace_reservation(
                current.portfolio_snapshot.reservations,
                next_reservation,
            ),
            position_references=_replace_reference(
                current.portfolio_snapshot.position_references,
                next_reference,
            ),
            event_sequence=current.event_sequence + 1,
            created_at=current.portfolio_snapshot.created_at,
            updated_at=updated_at,
            previous_lock_state=current.portfolio_snapshot.lock_state,
            warnings=current.portfolio_snapshot.warnings,
        )

        update_records[update_idempotency_key] = payload_hash
        event_records[portfolio_event_id] = payload_hash

        transition_records = dict(current.processed_p7_transition_hashes)
        transition_key = f"{position.position_id}|{sequence}"
        prior_transition = transition_records.get(transition_key)
        if prior_transition is not None and prior_transition != payload_hash:
            raise ValueError("P7 transition payload conflict")
        transition_records[transition_key] = payload_hash

        fill_records = dict(current.processed_p7_fill_hashes)
        for fill in position.exit_fills:
            fill_hash = hashlib.sha256(fill.to_json().encode("utf-8")).hexdigest()
            prior_fill = fill_records.get(fill.fill_id)
            if prior_fill is not None and prior_fill != fill_hash:
                raise ValueError("P7 fill payload conflict")
            fill_records[fill.fill_id] = fill_hash

        envelope = PaperPortfolioPersistenceSnapshotV1(
            portfolio_id=portfolio_id,
            portfolio_snapshot=next_snapshot,
            admission_idempotency_records=dict(current.admission_idempotency_records),
            update_idempotency_records=update_records,
            processed_portfolio_event_hashes=event_records,
            processed_p7_transition_hashes=transition_records,
            processed_p7_fill_hashes=fill_records,
            created_at=current.created_at,
            updated_at=updated_at,
            event_sequence=next_snapshot.event_sequence,
        )
        self.persistence_service.save(envelope)
        return envelope
