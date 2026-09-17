from __future__ import annotations

from datetime import datetime, timezone

from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.paper_portfolio import (
    aggregate_paper_portfolio,
    evaluate_paper_portfolio_locks,
    reserve_pending_paper_capital,
    validate_paper_portfolio_reconciliation,
)


NOW = datetime(2026, 7, 30, 1, 0, tzinfo=timezone.utc)


def make_policy(**overrides):
    values = dict(
        portfolio_policy_id="policy-1",
        policy_timestamp=NOW,
        maximum_concurrent_trades=3,
        maximum_total_deployed_capital=100_000.0,
        maximum_total_portfolio_risk_amount=10_000.0,
        maximum_daily_loss_amount=2_000.0,
        maximum_daily_drawdown_amount=3_000.0,
        maximum_instrument_risk_fraction=0.75,
        maximum_direction_risk_fraction=0.75,
        maximum_correlated_index_risk_fraction=0.60,
        maximum_expiry_risk_fraction=0.60,
        minimum_available_cash_reserve=10_000.0,
    )
    values.update(overrides)
    return PaperPortfolioPolicyV1(**values)


def test_lock_evaluator_is_unlocked_below_threshold():
    state = evaluate_paper_portfolio_locks(
        policy=make_policy(),
        trading_day_id="2026-07-30",
        daily_realized_net_pnl=-500.0,
        current_unrealized_pnl=-250.0,
        total_equity=99_250.0,
        previous_lock_state=None,
        evaluated_at=NOW,
    )
    assert state.loss_locked is False
    assert state.daily_loss_amount == 750.0


def test_lock_evaluator_latches_at_daily_loss_limit():
    state = evaluate_paper_portfolio_locks(
        policy=make_policy(),
        trading_day_id="2026-07-30",
        daily_realized_net_pnl=-2_000.0,
        current_unrealized_pnl=0.0,
        total_equity=98_000.0,
        previous_lock_state=None,
        evaluated_at=NOW,
    )
    assert state.loss_locked is True
    assert "DAILY_LOSS_LIMIT" in state.lock_reason_codes


def test_pending_reservation_and_empty_portfolio_aggregation():
    policy = make_policy()
    reservation = reserve_pending_paper_capital(
        reservation_id="reservation-1",
        portfolio_id="portfolio-1",
        admission_request_id="admission-1",
        admission_idempotency_key="key-1",
        integrated_trade_plan_result_id="integration-1",
        trade_plan_id="plan-1",
        capital_amount=20_000.0,
        risk_amount=2_000.0,
        initial_quantity=75,
        created_at=NOW,
    )
    snapshot = aggregate_paper_portfolio(
        portfolio_snapshot_id="snapshot-1",
        portfolio_id="portfolio-1",
        policy=policy,
        trading_day_id="2026-07-30",
        starting_capital=100_000.0,
        reservations=(reservation,),
        position_references=(),
        event_sequence=1,
        created_at=NOW,
        updated_at=NOW,
    )
    assert snapshot.reserved_capital == 20_000.0
    assert snapshot.deployed_capital == 0.0
    assert snapshot.committed_capital == 20_000.0
    assert snapshot.available_cash == 80_000.0
    assert snapshot.pending_plan_count == 1
    assert snapshot.concurrent_trade_count == 1
    assert snapshot.aggregate_pending_risk == 2_000.0


def test_empty_reconciliation_is_coherent():
    policy = make_policy()
    snapshot = aggregate_paper_portfolio(
        portfolio_snapshot_id="snapshot-empty",
        portfolio_id="portfolio-1",
        policy=policy,
        trading_day_id="2026-07-30",
        starting_capital=100_000.0,
        reservations=(),
        position_references=(),
        event_sequence=0,
        created_at=NOW,
        updated_at=NOW,
    )
    assert validate_paper_portfolio_reconciliation(
        portfolio_snapshot=snapshot,
        paper_trade_snapshots=(),
    ) == ()
