from datetime import datetime, timezone

from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.paper_orchestration.paper_state_factories import (
    build_initial_paper_portfolio_snapshot,
    build_initial_paper_trade_lifecycle_state,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def make_portfolio_policy():
    return PaperPortfolioPolicyV1(
        portfolio_policy_id="portfolio-policy-1",
        policy_timestamp=NOW,
        maximum_concurrent_trades=3,
        maximum_total_deployed_capital=100000.0,
        maximum_total_portfolio_risk_amount=10000.0,
        maximum_daily_loss_amount=5000.0,
        maximum_daily_drawdown_amount=5000.0,
        maximum_instrument_risk_fraction=1.0,
        maximum_direction_risk_fraction=1.0,
        maximum_correlated_index_risk_fraction=1.0,
        maximum_expiry_risk_fraction=1.0,
    )


def make_lifecycle_policy():
    return PaperTradeLifecyclePolicyV1(
        lifecycle_policy_id="lifecycle-policy-1",
        policy_timestamp=NOW,
        policy_source="P9_TEST",
        entry_timeout_seconds=300,
        maximum_observation_age_seconds=60,
        maximum_holding_seconds=3600,
    )


def test_initial_portfolio_uses_zero_event_sequence():
    snapshot = build_initial_paper_portfolio_snapshot(
        portfolio_snapshot_id="portfolio-snapshot-1",
        portfolio_id="portfolio-1",
        policy=make_portfolio_policy(),
        trading_day_id=NOW.date().isoformat(),
        starting_capital=100000.0,
        created_at=NOW,
    )

    assert snapshot.event_sequence == 0
    assert snapshot.available_cash == 100000.0
    assert snapshot.committed_capital == 0.0
    assert snapshot.reservations == ()
    assert snapshot.position_references == ()
    assert snapshot.execution_mode == "PAPER"
    assert snapshot.live_execution_eligible is False


def test_initial_lifecycle_is_planned_and_nonterminal():
    state = build_initial_paper_trade_lifecycle_state(
        lifecycle_state_id="lifecycle-state-1",
        trade_plan_id="trade-plan-1",
        integrated_trade_plan_result_id="integration-1",
        lifecycle_policy=make_lifecycle_policy(),
        created_at=NOW,
    )

    assert state.current_state == "PLANNED"
    assert state.previous_state is None
    assert state.transition_sequence == 0
    assert state.is_terminal is False
    assert state.execution_mode == "PAPER"


def test_initial_state_uses_policy_identity():
    policy = make_lifecycle_policy()
    state = build_initial_paper_trade_lifecycle_state(
        lifecycle_state_id="lifecycle-state-1",
        trade_plan_id="trade-plan-1",
        integrated_trade_plan_result_id="integration-1",
        lifecycle_policy=policy,
        created_at=NOW,
    )

    assert state.lifecycle_policy_id == policy.lifecycle_policy_id
