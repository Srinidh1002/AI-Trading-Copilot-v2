"""Pure deterministic multi-trade admission evaluator for P8."""
from __future__ import annotations

from dataclasses import replace

from services.contracts.paper_portfolio_admission_input_v1 import (
    PaperPortfolioAdmissionInputV1,
)
from services.contracts.paper_portfolio_admission_result_v1 import (
    PaperPortfolioAdmissionResultV1,
)
from .paper_capital_reservation_manager import reserve_pending_paper_capital
from .paper_portfolio_aggregation import aggregate_paper_portfolio


def _plan_fields(plan):
    capital = plan.capital_quantity_result
    option = plan.option_contract_selection_result
    selected = option.selected_contract
    contract = None if selected is None else selected.contract
    return {
        "integration_id": plan.integration_id,
        "trade_plan_id": capital.trade_plan_id,
        "capital_amount": capital.estimated_total_capital_requirement,
        "risk_amount": capital.estimated_risk_amount,
        "quantity": capital.planned_quantity,
        "underlying": option.underlying_symbol,
        "exchange": option.exchange,
        "direction": option.direction,
        "option_type": option.option_right,
        "expiry": None if contract is None else str(contract.expiry_date),
    }


def evaluate_paper_portfolio_admission(
    *,
    admission_result_id: str,
    input_value: PaperPortfolioAdmissionInputV1,
    resulting_snapshot_id: str,
) -> PaperPortfolioAdmissionResultV1:
    if type(input_value) is not PaperPortfolioAdmissionInputV1:
        raise TypeError("input_value must be exact PaperPortfolioAdmissionInputV1")

    plan = input_value.integrated_trade_plan_result
    snapshot = input_value.current_portfolio_snapshot
    policy = input_value.portfolio_policy
    blockers: list[str] = []
    reasons: list[str] = []

    if plan.status != "READY":
        blockers.append("PLAN_NOT_READY")

    try:
        fields = _plan_fields(plan)
    except Exception:
        fields = None
        blockers.append("CAPITAL_EVIDENCE_INCOMPLETE")

    if snapshot.blockers:
        blockers.append("PORTFOLIO_CORRUPT")
    if snapshot.lock_state.admission_locked:
        blockers.append("PORTFOLIO_LOCKED")

    if blockers:
        return PaperPortfolioAdmissionResultV1(
            admission_result_id=admission_result_id,
            admission_request_id=input_value.admission_request_id,
            admission_idempotency_key=input_value.admission_idempotency_key,
            admission_payload_hash=input_value.semantic_payload_hash,
            portfolio_event_id=input_value.portfolio_event_id,
            portfolio_id=input_value.portfolio_id,
            portfolio_policy_id=policy.portfolio_policy_id,
            trading_day_id=input_value.trading_day_id,
            integration_id=plan.integration_id,
            trade_plan_id=(
                getattr(plan.capital_quantity_result, "trade_plan_id", "UNKNOWN")
            ),
            requested_reservation_id=input_value.requested_reservation_id,
            status="BLOCKED",
            approved=False,
            reservation_amount=0.0,
            reserved_risk_amount=0.0,
            projected_available_cash=snapshot.available_cash,
            projected_reserved_capital=snapshot.reserved_capital,
            projected_deployed_capital=snapshot.deployed_capital,
            projected_committed_capital=snapshot.committed_capital,
            projected_concurrent_trade_count=snapshot.concurrent_trade_count,
            projected_aggregate_committed_risk=snapshot.aggregate_committed_risk,
            evaluated_at=input_value.evaluated_at,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    capital_amount = float(fields["capital_amount"])
    risk_amount = float(fields["risk_amount"])
    quantity = int(fields["quantity"])

    projected_concurrent = snapshot.concurrent_trade_count + 1
    projected_reserved = snapshot.reserved_capital + capital_amount
    projected_committed = snapshot.committed_capital + capital_amount
    projected_available = snapshot.total_equity - projected_committed
    projected_risk = snapshot.aggregate_committed_risk + risk_amount

    if projected_concurrent > policy.maximum_concurrent_trades:
        reasons.append("CONCURRENT_TRADE_LIMIT")
    if projected_available < policy.minimum_available_cash_reserve:
        reasons.append("MINIMUM_RESERVE_BREACH")
    if projected_available < 0:
        reasons.append("AVAILABLE_CASH_INSUFFICIENT")
    if projected_committed > policy.maximum_total_deployed_capital:
        reasons.append("DEPLOYED_CAPITAL_LIMIT")
    if projected_risk > policy.maximum_total_portfolio_risk_amount:
        reasons.append("TOTAL_RISK_LIMIT")

    instrument_key = f"{fields['underlying']}|{fields['exchange']}"
    current_instrument = snapshot.exposure.instrument_risk.get(instrument_key, 0.0)
    if (
        current_instrument + risk_amount
        > policy.maximum_total_portfolio_risk_amount
        * policy.maximum_instrument_risk_fraction
    ):
        reasons.append("INSTRUMENT_RISK_LIMIT")

    current_direction = snapshot.exposure.direction_risk.get(fields["direction"], 0.0)
    if (
        current_direction + risk_amount
        > policy.maximum_total_portfolio_risk_amount
        * policy.maximum_direction_risk_fraction
    ):
        reasons.append("DIRECTION_RISK_LIMIT")

    if fields["underlying"] in {"NIFTY", "SENSEX"}:
        correlated_key = f"NIFTY+SENSEX|{fields['direction']}"
        current_correlated = snapshot.exposure.correlated_index_direction_risk.get(
            correlated_key, 0.0
        )
        if (
            current_correlated + risk_amount
            > policy.maximum_total_portfolio_risk_amount
            * policy.maximum_correlated_index_risk_fraction
        ):
            reasons.append("CORRELATED_INDEX_RISK_LIMIT")

    if fields["expiry"] is not None:
        current_expiry = snapshot.exposure.expiry_risk.get(fields["expiry"], 0.0)
        if (
            current_expiry + risk_amount
            > policy.maximum_total_portfolio_risk_amount
            * policy.maximum_expiry_risk_fraction
        ):
            reasons.append("EXPIRY_RISK_LIMIT")

    if reasons:
        return PaperPortfolioAdmissionResultV1(
            admission_result_id=admission_result_id,
            admission_request_id=input_value.admission_request_id,
            admission_idempotency_key=input_value.admission_idempotency_key,
            admission_payload_hash=input_value.semantic_payload_hash,
            portfolio_event_id=input_value.portfolio_event_id,
            portfolio_id=input_value.portfolio_id,
            portfolio_policy_id=policy.portfolio_policy_id,
            trading_day_id=input_value.trading_day_id,
            integration_id=fields["integration_id"],
            trade_plan_id=fields["trade_plan_id"],
            requested_reservation_id=input_value.requested_reservation_id,
            status="NO_CAPACITY",
            approved=False,
            reservation_amount=capital_amount,
            reserved_risk_amount=risk_amount,
            projected_available_cash=projected_available,
            projected_reserved_capital=projected_reserved,
            projected_deployed_capital=snapshot.deployed_capital,
            projected_committed_capital=projected_committed,
            projected_concurrent_trade_count=projected_concurrent,
            projected_aggregate_committed_risk=projected_risk,
            evaluated_at=input_value.evaluated_at,
            decision_reasons=tuple(dict.fromkeys(reasons)),
        )

    reservation = reserve_pending_paper_capital(
        reservation_id=input_value.requested_reservation_id,
        portfolio_id=input_value.portfolio_id,
        admission_request_id=input_value.admission_request_id,
        admission_idempotency_key=input_value.admission_idempotency_key,
        integrated_trade_plan_result_id=fields["integration_id"],
        trade_plan_id=fields["trade_plan_id"],
        capital_amount=capital_amount,
        risk_amount=risk_amount,
        initial_quantity=quantity,
        created_at=input_value.evaluated_at,
    )
    resulting_snapshot = aggregate_paper_portfolio(
        portfolio_snapshot_id=resulting_snapshot_id,
        portfolio_id=snapshot.portfolio_id,
        policy=policy,
        trading_day_id=snapshot.trading_day_id,
        starting_capital=snapshot.starting_capital,
        reservations=snapshot.reservations + (reservation,),
        position_references=snapshot.position_references,
        event_sequence=snapshot.event_sequence + 1,
        created_at=snapshot.created_at,
        updated_at=input_value.evaluated_at,
        previous_lock_state=snapshot.lock_state,
        warnings=snapshot.warnings,
    )

    return PaperPortfolioAdmissionResultV1(
        admission_result_id=admission_result_id,
        admission_request_id=input_value.admission_request_id,
        admission_idempotency_key=input_value.admission_idempotency_key,
        admission_payload_hash=input_value.semantic_payload_hash,
        portfolio_event_id=input_value.portfolio_event_id,
        portfolio_id=input_value.portfolio_id,
        portfolio_policy_id=policy.portfolio_policy_id,
        trading_day_id=input_value.trading_day_id,
        integration_id=fields["integration_id"],
        trade_plan_id=fields["trade_plan_id"],
        requested_reservation_id=input_value.requested_reservation_id,
        status="APPROVED",
        approved=True,
        reservation_amount=capital_amount,
        reserved_risk_amount=risk_amount,
        projected_available_cash=resulting_snapshot.available_cash,
        projected_reserved_capital=resulting_snapshot.reserved_capital,
        projected_deployed_capital=resulting_snapshot.deployed_capital,
        projected_committed_capital=resulting_snapshot.committed_capital,
        projected_concurrent_trade_count=resulting_snapshot.concurrent_trade_count,
        projected_aggregate_committed_risk=resulting_snapshot.aggregate_committed_risk,
        evaluated_at=input_value.evaluated_at,
        resulting_reservation=reservation,
        resulting_snapshot=resulting_snapshot,
    )
