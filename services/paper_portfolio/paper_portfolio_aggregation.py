"""Pure deterministic P8 portfolio aggregation."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from services.contracts.paper_capital_reservation_v1 import PaperCapitalReservationV1
from services.contracts.paper_portfolio_exposure_v1 import PaperPortfolioExposureV1
from services.contracts.paper_portfolio_lock_state_v1 import PaperPortfolioLockStateV1
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_portfolio_position_reference_v1 import (
    PaperPortfolioPositionReferenceV1,
)
from services.contracts.paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1
from .paper_portfolio_lock_evaluator import evaluate_paper_portfolio_locks


def _correlated_key(underlying_symbol: str, direction: str) -> str | None:
    if underlying_symbol in {"NIFTY", "SENSEX"}:
        return f"NIFTY+SENSEX|{direction}"
    return None


def build_paper_portfolio_exposure(
    *,
    reservations: tuple[PaperCapitalReservationV1, ...],
    position_references: tuple[PaperPortfolioPositionReferenceV1, ...],
) -> PaperPortfolioExposureV1:
    reference_by_reservation = {
        reference.reservation_id: reference for reference in position_references
    }
    instrument: dict[str, float] = defaultdict(float)
    direction: dict[str, float] = defaultdict(float)
    expiry: dict[str, float] = defaultdict(float)
    correlated: dict[str, float] = defaultdict(float)

    for reservation in sorted(reservations, key=lambda item: item.reservation_id):
        if reservation.reservation_status == "RELEASED":
            continue
        reference = reference_by_reservation.get(reservation.reservation_id)
        if reference is None:
            continue
        risk = reservation.remaining_risk_amount
        instrument[f"{reference.underlying_symbol}|{reference.exchange}"] += risk
        direction[reference.economic_direction] += risk
        expiry[reference.expiry] += risk
        key = _correlated_key(reference.underlying_symbol, reference.economic_direction)
        if key is not None:
            correlated[key] += risk

    return PaperPortfolioExposureV1(
        instrument_risk=dict(instrument),
        direction_risk=dict(direction),
        expiry_risk=dict(expiry),
        correlated_index_direction_risk=dict(correlated),
        total_instrument_risk=math.fsum(instrument.values()),
        total_direction_risk=math.fsum(direction.values()),
        total_expiry_risk=math.fsum(expiry.values()),
        total_correlated_index_direction_risk=math.fsum(correlated.values()),
    )


def aggregate_paper_portfolio(
    *,
    portfolio_snapshot_id: str,
    portfolio_id: str,
    policy: PaperPortfolioPolicyV1,
    trading_day_id: str,
    starting_capital: float,
    reservations: tuple[PaperCapitalReservationV1, ...],
    position_references: tuple[PaperPortfolioPositionReferenceV1, ...],
    event_sequence: int,
    created_at: datetime,
    updated_at: datetime,
    previous_lock_state: PaperPortfolioLockStateV1 | None = None,
    blockers: tuple[str, ...] = (),
    decision_reasons: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> PaperPortfolioSnapshotV1:
    if type(policy) is not PaperPortfolioPolicyV1:
        raise TypeError("policy must be exact PaperPortfolioPolicyV1")
    if len({item.reservation_id for item in reservations}) != len(reservations):
        raise ValueError("duplicate reservation")
    if len({item.position_id for item in position_references}) != len(position_references):
        raise ValueError("duplicate position reference")

    ordered_reservations = tuple(sorted(reservations, key=lambda item: item.reservation_id))
    ordered_positions = tuple(sorted(position_references, key=lambda item: item.position_id))

    reserved = math.fsum(
        item.remaining_capital_amount
        for item in ordered_reservations
        if item.reservation_status == "PENDING_HOLD"
    )
    deployed = math.fsum(
        item.remaining_capital_amount
        for item in ordered_reservations
        if item.reservation_status == "ACTIVE"
    )
    active_risk = math.fsum(
        item.remaining_risk_amount
        for item in ordered_reservations
        if item.reservation_status == "ACTIVE"
    )
    pending_risk = math.fsum(
        item.remaining_risk_amount
        for item in ordered_reservations
        if item.reservation_status == "PENDING_HOLD"
    )
    realized = math.fsum(item.realized_net_pnl for item in ordered_positions)
    unrealized = math.fsum(
        item.unrealized_pnl for item in ordered_positions if not item.is_terminal
    )
    total_pnl = realized + unrealized
    total_equity = float(starting_capital) + total_pnl
    committed = reserved + deployed
    exposure = build_paper_portfolio_exposure(
        reservations=ordered_reservations,
        position_references=ordered_positions,
    )
    lock_state = evaluate_paper_portfolio_locks(
        policy=policy,
        trading_day_id=trading_day_id,
        daily_realized_net_pnl=realized,
        current_unrealized_pnl=unrealized,
        total_equity=total_equity,
        previous_lock_state=previous_lock_state,
        evaluated_at=updated_at,
    )

    return PaperPortfolioSnapshotV1(
        portfolio_snapshot_id=portfolio_snapshot_id,
        portfolio_id=portfolio_id,
        portfolio_policy_id=policy.portfolio_policy_id,
        trading_day_id=trading_day_id,
        starting_capital=starting_capital,
        available_cash=total_equity - committed,
        reserved_capital=reserved,
        deployed_capital=deployed,
        committed_capital=committed,
        realized_net_pnl=realized,
        unrealized_pnl=unrealized,
        total_pnl=total_pnl,
        total_equity=total_equity,
        portfolio_return_fraction=total_pnl / float(starting_capital),
        capital_utilization_fraction=committed / float(starting_capital),
        open_position_count=sum(1 for item in ordered_positions if not item.is_terminal),
        pending_plan_count=sum(
            1 for item in ordered_reservations if item.reservation_status == "PENDING_HOLD"
        ),
        concurrent_trade_count=(
            sum(1 for item in ordered_positions if not item.is_terminal)
            + sum(
                1
                for item in ordered_reservations
                if item.reservation_status == "PENDING_HOLD"
            )
        ),
        aggregate_active_risk=active_risk,
        aggregate_pending_risk=pending_risk,
        aggregate_committed_risk=active_risk + pending_risk,
        reservations=ordered_reservations,
        position_references=ordered_positions,
        exposure=exposure,
        lock_state=lock_state,
        event_sequence=event_sequence,
        created_at=created_at,
        updated_at=updated_at,
        blockers=blockers,
        decision_reasons=decision_reasons,
        warnings=warnings,
    )
