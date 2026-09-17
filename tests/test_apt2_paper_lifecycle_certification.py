"""APT Gates 5–7: durable, PAPER-only entry and monitoring certification."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
    ExistingPositionMonitoringInputV1,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleExecutor,
    NewEntryPaperLifecycleInputV1,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)
from services.paper_trading.paper_trade_replay_coordinator import (
    PaperTradeReplayCoordinator,
)
from tests.p7_fixture_helpers import NOW, make_observation, make_policy
from tests.p8_portfolio_harness import (
    make_cost_complete_integrated,
    make_p8_policy,
)


PORTFOLIO_ID = "apt2-paper-portfolio"
PAPER_TRADE_ID = "apt2-paper-trade"


def _services(tmp_path):
    portfolio_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(tmp_path / "p8.json")
    )
    trade_service = PaperTradePersistenceService(
        PaperTradeRepository(tmp_path / "p7.json")
    )
    return portfolio_service, trade_service


def _ready_three_lot_plan():
    plan = make_cost_complete_integrated()
    capital = plan.capital_quantity_result

    capital = replace(
        capital,
        risk_based_lot_limit=10,
        upstream_affordable_lot_limit=3,
        deployable_capital_affordable_lot_limit=36,
        planned_lot_count=3,
        lot_size=25,
        planned_quantity=75,
        estimated_one_lot_premium_cost=2500.0,
        estimated_premium_outlay=7500.0,
        per_lot_risk_amount=250.0,
        estimated_risk_amount=750.0,
        target_allocation_enabled=True,
        target_1_lot_count=1,
        target_2_lot_count=1,
        target_3_lot_count=1,
        runner_lot_count=0,
        estimated_brokerage=0.0,
        estimated_exchange_transaction_charges=0.0,
        estimated_clearing_charges=0.0,
        estimated_stt=0.0,
        estimated_sebi_charges=0.0,
        estimated_stamp_duty=0.0,
        estimated_gst=0.0,
        estimated_slippage=0.0,
        estimated_total_trading_cost=0.0,
        estimated_total_capital_requirement=7500.0,
        cost_adjusted_capital_feasible=True,
    )

    return replace(
        plan,
        capital_quantity_result=capital,
    )


def _entry_input():
    policy = make_p8_policy(
        portfolio_policy_id="apt2-p8-policy",
        minimum_available_cash_reserve=0.0,
    )

    lifecycle_policy = make_policy(
        lifecycle_policy_id="apt2-p7-policy",
        allow_partial_exits=True,
        entry_timeout_seconds=300,
        maximum_observation_age_seconds=300,
        maximum_holding_seconds=1800,
    )

    observation = make_observation(
        observation_id="apt2-entry-observation",
        option_last_price=100.0,
        option_open=100.0,
        option_low=99.0,
        option_high=101.0,
        option_close=100.0,
    )

    return NewEntryPaperLifecycleInputV1(
        portfolio_id=PORTFOLIO_ID,
        initial_portfolio_snapshot_id="apt2-p8-initial",
        admission_result_id="apt2-admission-result",
        admission_request_id="apt2-admission-request",
        admission_idempotency_key="apt2-admission-key",
        admission_portfolio_event_id="apt2-admission-event",
        requested_reservation_id="apt2-reservation",
        paper_trade_id=PAPER_TRADE_ID,
        paper_trade_adapter_idempotency_key="apt2-paper-trade-key",
        initial_lifecycle_state_id="apt2-initial-state",
        resulting_lifecycle_state_id="apt2-open-state",
        requested_transition_id="apt2-entry-transition",
        position_id="apt2-position",
        entry_fill_id="apt2-entry-fill",
        activation_result_snapshot_id="apt2-p8-open",
        activation_portfolio_event_id="apt2-activation-event",
        activation_update_idempotency_key="apt2-activation-key",
        trading_day_id="2026-01-08",
        starting_capital=100_000.0,
        evaluated_at=NOW,
        integrated_trade_plan_result=_ready_three_lot_plan(),
        portfolio_policy=policy,
        lifecycle_policy=lifecycle_policy,
        observation=observation,
        execution_mode="PAPER",
        live_execution_eligible=False,
    )


def _open_entry(tmp_path):
    portfolios, trades = _services(tmp_path)

    executor = NewEntryPaperLifecycleExecutor(
        portfolio_persistence_service=portfolios,
        trade_persistence_service=trades,
    )

    result = executor.execute(_entry_input())

    assert result.status == "OPEN"
    assert result.paper_action_occurred is True
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.p7_snapshot is not None
    assert result.p8_snapshot is not None

    return portfolios, trades, executor, result


def _monitor_input(
    *,
    p7,
    p8_policy,
    observation,
    sequence,
):
    timestamp = observation.observed_at

    evaluation = PaperTradePositionEvaluationInputV1(
        position=p7.position,
        lifecycle_policy=p7.lifecycle_policy,
        lifecycle_state=p7.lifecycle_state,
        observation=observation,
        evaluation_timestamp=timestamp,
        requested_transition_id=(
            f"apt2-monitor-transition-{sequence}"
        ),
        resulting_lifecycle_state_id=(
            f"apt2-monitor-state-{sequence}"
        ),
        evaluation_result_id=(
            f"apt2-monitor-result-{sequence}"
        ),
        exit_fill_ids=tuple(
            f"apt2-exit-{sequence}-{number}"
            for number in range(1, 4)
        ),
        pnl_evidence_id=f"apt2-pnl-{sequence}",
    )

    return ExistingPositionMonitoringInputV1(
        portfolio_id=PORTFOLIO_ID,
        result_snapshot_id=f"apt2-p8-monitor-{sequence}",
        portfolio_event_id=f"apt2-monitor-event-{sequence}",
        update_idempotency_key=f"apt2-monitor-key-{sequence}",
        updated_at=timestamp,
        portfolio_policy=p8_policy,
        p7_snapshot=p7,
        evaluation_input=evaluation,
    )


def _observation(
    *,
    observation_id,
    price,
    seconds,
):
    timestamp = NOW + timedelta(seconds=seconds)

    return make_observation(
        observation_id=observation_id,
        observed_at=timestamp,
        received_at=timestamp,
        option_last_price=price,
        option_open=price,
        option_low=price - 1.0,
        option_high=price + 1.0,
        option_close=price,
    )


def _monitor_executor(portfolios, trades):
    return ExistingPositionMonitoringExecutor(
        trade_replay_coordinator=PaperTradeReplayCoordinator(
            trades
        ),
        portfolio_lifecycle_coordinator=(
            PaperPortfolioLifecycleCoordinator(portfolios)
        ),
    )


def test_deterministic_paper_open_persists_without_broker_submission(
    tmp_path,
):
    portfolios, trades, executor, result = _open_entry(
        tmp_path
    )

    assert result.paper_action_occurred is True
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.p7_snapshot is not None
    assert result.p8_snapshot is not None

    persisted_trade = trades.get(PAPER_TRADE_ID)
    persisted_portfolio = portfolios.get(PORTFOLIO_ID)

    assert persisted_trade is not None
    assert persisted_portfolio is not None
    assert persisted_trade.execution_mode == "PAPER"
    assert persisted_trade.live_execution_eligible is False
    assert persisted_portfolio.execution_mode == "PAPER"
    assert persisted_portfolio.live_execution_eligible is False

    assert executor.broker_order_submission is False


def test_same_entry_is_idempotent_and_restart_recovers_one_active_position(
    tmp_path,
):
    portfolios, trades, executor, first = _open_entry(tmp_path)

    with pytest.raises(
        ValueError,
        match="duplicate reservation",
    ):
        executor.execute(_entry_input())

    assert first.status == "OPEN"
    assert len(trades.list_all()) == 1

    persisted = trades.get(PAPER_TRADE_ID)
    assert persisted is not None
    assert persisted.position.position_id == "apt2-position"
    assert len(persisted.position.exit_fills) == 0

    persisted_portfolio = portfolios.get(PORTFOLIO_ID)
    assert persisted_portfolio is not None
    assert len(
        persisted_portfolio.portfolio_snapshot.reservations
    ) == 1
    assert len(
        persisted_portfolio.portfolio_snapshot.position_references
    ) == 1

    restarted_trades = PaperTradePersistenceService(
        PaperTradeRepository(tmp_path / "p7.json")
    )

    active = PaperTradeRecoveryService(
        restarted_trades
    ).recover_active()

    assert len(active) == 1
    assert active[0].paper_trade_id == PAPER_TRADE_ID
    assert active[0].execution_mode == "PAPER"
    assert active[0].live_execution_eligible is False
    portfolios, trades, executor, first = _open_entry(
        tmp_path
    )

    second = executor.execute(_entry_input())

    assert first.status == "OPEN"
    assert second.status == "OPEN"

    all_trades = trades.list_all()
    assert len(all_trades) == 1

    persisted = trades.get(PAPER_TRADE_ID)
    assert persisted is not None
    assert persisted.position.position_id == "apt2-position"
    assert len(persisted.position.exit_fills) == 0

    persisted_portfolio = portfolios.get(PORTFOLIO_ID)
    assert persisted_portfolio is not None
    assert len(
        persisted_portfolio.portfolio_snapshot.reservations
    ) == 1
    assert len(
        persisted_portfolio.portfolio_snapshot.position_references
    ) == 1

    restarted_trades = PaperTradePersistenceService(
        PaperTradeRepository(tmp_path / "p7.json")
    )

    active = PaperTradeRecoveryService(
        restarted_trades
    ).recover_active()

    assert len(active) == 1
    assert active[0].paper_trade_id == PAPER_TRADE_ID
    assert active[0].execution_mode == "PAPER"
    assert active[0].live_execution_eligible is False


def test_position_monitoring_transitions_are_paper_only(
    tmp_path,
):
    portfolios, trades, _, opened = _open_entry(tmp_path)
    monitor = _monitor_executor(portfolios, trades)
    policy = _entry_input().portfolio_policy

    p7 = opened.p7_snapshot
    assert p7 is not None

    hold = monitor.execute(
        _monitor_input(
            p7=p7,
            p8_policy=policy,
            observation=_observation(
                observation_id="apt2-hold",
                price=105.0,
                seconds=1,
            ),
            sequence=1,
        )
    )

    assert hold.status in {
        "HOLD_UPDATED",
        "HOLD_NO_CHANGE",
    }

    persisted_after_hold = trades.get(PAPER_TRADE_ID)
    assert persisted_after_hold is not None
    assert len(
        persisted_after_hold.position.exit_fills
    ) == 0

    target_1 = monitor.execute(
        _monitor_input(
            p7=persisted_after_hold,
            p8_policy=policy,
            observation=_observation(
                observation_id="apt2-target-1",
                price=110.0,
                seconds=2,
            ),
            sequence=2,
        )
    )

    assert target_1.status == "PARTIAL_EXIT"
    assert target_1.paper_action_occurred is True
    assert target_1.p7_snapshot is not None
    assert (
        target_1.p7_snapshot.position.remaining_quantity
        == 50
    )
    assert target_1.evaluation_result.pnl_evidence is not None

    target_2 = monitor.execute(
        _monitor_input(
            p7=target_1.p7_snapshot,
            p8_policy=policy,
            observation=_observation(
                observation_id="apt2-target-2",
                price=120.0,
                seconds=3,
            ),
            sequence=3,
        )
    )

    assert target_2.status == "PARTIAL_EXIT"
    assert target_2.paper_action_occurred is True
    assert target_2.p7_snapshot is not None
    assert (
        target_2.p7_snapshot.position.remaining_quantity
        == 25
    )

    final_target = monitor.execute(
        _monitor_input(
            p7=target_2.p7_snapshot,
            p8_policy=policy,
            observation=_observation(
                observation_id="apt2-target-3",
                price=130.0,
                seconds=4,
            ),
            sequence=4,
        )
    )

    assert final_target.status == "CLOSED"
    assert final_target.paper_action_occurred is True
    assert final_target.p7_snapshot is not None
    assert final_target.p8_snapshot is not None

    assert (
        final_target.p7_snapshot.position.remaining_quantity
        == 0
    )
    assert (
        final_target.p7_snapshot.lifecycle_state.is_terminal
        is True
    )
    assert final_target.p8_snapshot.execution_mode == "PAPER"
    assert (
        final_target.p8_snapshot.live_execution_eligible
        is False
    )

    persisted = trades.get(PAPER_TRADE_ID)
    assert persisted is not None
    assert len(persisted.position.exit_fills) == 3
    assert persisted.execution_mode == "PAPER"
    assert persisted.live_execution_eligible is False


def test_same_entry_is_idempotent_and_restart_recovers_one_active_position(
    tmp_path,
):
    portfolios, trades, executor, first = _open_entry(tmp_path)

    with pytest.raises(
        ValueError,
        match="duplicate reservation",
    ):
        executor.execute(_entry_input())

    assert first.status == "OPEN"
    assert len(trades.list_all()) == 1

    persisted = trades.get(PAPER_TRADE_ID)
    assert persisted is not None
    assert persisted.position.position_id == "apt2-position"
    assert len(persisted.position.exit_fills) == 0

    persisted_portfolio = portfolios.get(PORTFOLIO_ID)
    assert persisted_portfolio is not None
    assert len(
        persisted_portfolio.portfolio_snapshot.reservations
    ) == 1
    assert len(
        persisted_portfolio.portfolio_snapshot.position_references
    ) == 1

    restarted_trades = PaperTradePersistenceService(
        PaperTradeRepository(tmp_path / "p7.json")
    )

    active = PaperTradeRecoveryService(
        restarted_trades
    ).recover_active()

    assert len(active) == 1
    assert active[0].paper_trade_id == PAPER_TRADE_ID
    assert active[0].execution_mode == "PAPER"
    assert active[0].live_execution_eligible is False


def test_stop_loss_monitoring_closes_a_separate_open_fixture(
    tmp_path,
):
    portfolios, trades, _, opened = _open_entry(tmp_path)
    monitor = _monitor_executor(portfolios, trades)

    p7 = opened.p7_snapshot
    assert p7 is not None

    stopped = monitor.execute(
        _monitor_input(
            p7=p7,
            p8_policy=_entry_input().portfolio_policy,
            observation=_observation(
                observation_id="apt2-stop",
                price=90.0,
                seconds=1,
            ),
            sequence="stop",
        )
    )

    assert stopped.status == "CLOSED"
    assert stopped.paper_action_occurred is True
    assert stopped.p7_snapshot is not None
    assert stopped.p8_snapshot is not None

    assert (
        stopped.p7_snapshot.position.remaining_quantity
        == 0
    )
    assert (
        stopped.p7_snapshot.lifecycle_state.current_state
        == "CLOSED_STOP"
    )
    assert stopped.p7_snapshot.execution_mode == "PAPER"
    assert stopped.p7_snapshot.live_execution_eligible is False
    assert stopped.p8_snapshot.execution_mode == "PAPER"
    assert stopped.p8_snapshot.live_execution_eligible is False


def test_paper_only_constructor_invariants_remain_enforced():
    valid = _entry_input()

    with pytest.raises(
        ValueError,
        match="execution_mode must be PAPER",
    ):
        replace(
            valid,
            execution_mode="LIVE",
        )

    with pytest.raises(
        ValueError,
        match="live execution is not eligible",
    ):
        replace(
            valid,
            live_execution_eligible=True,
        )