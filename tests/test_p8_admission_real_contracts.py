from __future__ import annotations

from dataclasses import replace

from services.contracts.paper_portfolio_admission_input_v1 import (
    PaperPortfolioAdmissionInputV1,
)
from services.paper_portfolio import (
    aggregate_paper_portfolio,
    evaluate_paper_portfolio_admission,
)
from tests.p8_portfolio_harness import (
    NOW,
    PORTFOLIO_ID,
    TRADING_DAY_ID,
    make_cost_complete_integrated,
    make_initial_p8_snapshot,
    make_p8_policy,
)


def make_empty_snapshot(policy):
    return aggregate_paper_portfolio(
        portfolio_snapshot_id="empty-snapshot",
        portfolio_id=PORTFOLIO_ID,
        policy=policy,
        trading_day_id=TRADING_DAY_ID,
        starting_capital=100_000.0,
        reservations=(),
        position_references=(),
        event_sequence=0,
        created_at=NOW,
        updated_at=NOW,
    )


def make_input(*, policy=None, snapshot=None, key="admission-key-real"):
    policy = policy or make_p8_policy()
    snapshot = snapshot or make_empty_snapshot(policy)
    return PaperPortfolioAdmissionInputV1(
        admission_request_id="admission-request-real",
        admission_idempotency_key=key,
        portfolio_event_id="portfolio-event-real",
        portfolio_id=PORTFOLIO_ID,
        requested_reservation_id="reservation-real",
        evaluated_at=NOW,
        trading_day_id=TRADING_DAY_ID,
        integrated_trade_plan_result=make_cost_complete_integrated(),
        current_portfolio_snapshot=snapshot,
        portfolio_policy=policy,
    )


def test_real_ready_plan_is_approved_with_exact_p6_amounts():
    input_value = make_input()
    result = evaluate_paper_portfolio_admission(
        admission_result_id="admission-result-real",
        input_value=input_value,
        resulting_snapshot_id="approved-snapshot",
    )

    capital = input_value.integrated_trade_plan_result.capital_quantity_result
    assert result.status == "APPROVED"
    assert result.approved is True
    assert result.reservation_amount == capital.estimated_total_capital_requirement
    assert result.reserved_risk_amount == capital.estimated_risk_amount
    assert result.resulting_reservation.remaining_quantity == capital.planned_quantity
    assert result.resulting_snapshot.reserved_capital == result.reservation_amount
    assert result.resulting_snapshot.event_sequence == 1


def test_concurrent_trade_limit_returns_no_capacity():
    policy = make_p8_policy(maximum_concurrent_trades=1)
    snapshot = make_initial_p8_snapshot(policy=policy)
    assert snapshot.concurrent_trade_count == 1

    input_value = make_input(policy=policy, snapshot=snapshot)
    result = evaluate_paper_portfolio_admission(
        admission_result_id="admission-result-limit",
        input_value=input_value,
        resulting_snapshot_id="unused-snapshot",
    )

    assert result.status == "NO_CAPACITY"
    assert result.approved is False
    assert "CONCURRENT_TRADE_LIMIT" in result.decision_reasons
    assert result.resulting_reservation is None
    assert result.resulting_snapshot is None


def test_loss_lock_blocks_admission():
    policy = make_p8_policy()
    snapshot = make_empty_snapshot(policy)
    locked = snapshot.lock_state.__class__(
        trading_day_id=snapshot.trading_day_id,
        loss_locked=True,
        profit_locked=False,
        lock_reason_codes=("DAILY_LOSS_LIMIT",),
        daily_total_pnl=-2_000.0,
        daily_realized_net_pnl=-2_000.0,
        daily_loss_amount=2_000.0,
        intraday_peak_equity=100_000.0,
        daily_drawdown_amount=2_000.0,
        evaluated_at=NOW,
        loss_locked_at=NOW,
    )
    snapshot = replace(snapshot, lock_state=locked)
    input_value = make_input(policy=policy, snapshot=snapshot)

    result = evaluate_paper_portfolio_admission(
        admission_result_id="admission-result-locked",
        input_value=input_value,
        resulting_snapshot_id="unused-snapshot",
    )
    assert result.status == "BLOCKED"
    assert "PORTFOLIO_LOCKED" in result.blockers
