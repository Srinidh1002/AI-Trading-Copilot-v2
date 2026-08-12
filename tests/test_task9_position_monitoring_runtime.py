from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_position_monitoring_runtime import (
    execute_task9_position_monitoring,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    execute_task9_selected_market_lifecycle,
)
from services.paper_orchestration.continuous_position_monitoring_runtime import (
    execute_continuous_position_monitoring,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)


PORTFOLIO_ID = "task916-monitoring-paper-portfolio"


def _restart_policy_store(tmp_path):
    return Task9PaperPortfolioPolicyStore(
        tmp_path / "task916-portfolio-policies.json"
    )


def _restart_services(root):
    return (
        PaperPortfolioPersistenceService(
            PaperPortfolioRepository(
                root / "p8_portfolios.json"
            )
        ),
        PaperTradePersistenceService(
            PaperTradeRepository(
                root / "p7_trades.json"
            )
        ),
    )


def _restart_task9_stores(tmp_path):
    return (
        PredictionLedger(
            tmp_path / "task916-prediction-ledger.json"
        ),
        Task9PredictionLifecycleContextStore(
            tmp_path / "task916-lifecycle-context.json"
        ),
        Task9PredictionPaperTradeBindingStore(
            tmp_path / "task916-bindings.json"
        ),
        Task9PredictionObservationWindowStore(
            tmp_path / "task916-observations.json"
        ),
    )


def _monitor_kwargs(
    *,
    portfolio_service,
    trade_service,
    portfolio_policy,
    paper_trade_id,
    observation,
):
    return {
        "portfolio_id": PORTFOLIO_ID,
        "paper_trade_id": paper_trade_id,
        "portfolio_policy": portfolio_policy,
        "observation": observation,
        "evaluation_timestamp": observation.observed_at,
        "requested_transition_id": (
            "task916-monitor-transition-t2"
        ),
        "resulting_lifecycle_state_id": (
            "task916-monitor-state-t2"
        ),
        "evaluation_result_id": (
            "task916-monitor-evaluation-t2"
        ),
        "exit_fill_ids": (
            "task916-monitor-exit-t2-1",
            "task916-monitor-exit-t2-2",
            "task916-monitor-exit-t2-3",
            "task916-monitor-exit-t2-4",
        ),
        "pnl_evidence_id": (
            "task916-monitor-pnl-t2"
        ),
        "result_snapshot_id": (
            "task916-monitor-portfolio-t2"
        ),
        "portfolio_event_id": (
            "task916-monitor-event-t2"
        ),
        "update_idempotency_key": (
            "task916-monitor-update-t2"
        ),
        "portfolio_persistence_service": (
            portfolio_service
        ),
        "trade_persistence_service": (
            trade_service
        ),
    }


def test_task9_real_p7_restart_monitoring_records_allocated_target(
    tmp_path,
):
    harness = build_task916_real_runtime_harness(
        tmp_path,
        market="NIFTY",
    )

    persistence_root = (
        tmp_path
        / "task916-runtime"
    )

    portfolio_policy_store = (
        Task9PaperPortfolioPolicyStore(
            tmp_path
            / "task916-portfolio-policies.json"
        )
    )

    entry_result = execute_task9_selected_market_lifecycle(
        official_run_id="task916-official-run",
        binding_store=harness.binding_store,
        prediction_id=(
            harness.selected_prediction.prediction_id
        ),
        prediction_ledger=harness.prediction_ledger,
        lifecycle_context_store=(
            harness.lifecycle_context_store
        ),
        observation_store=(
            harness.observation_store
        ),
        portfolio_policy_store=(
            portfolio_policy_store
        ),
        selected_cycle=harness.selected_cycle,
        selected_planning=harness.selected_planning,
        available_capital=300000.0,
        evaluated_at=harness.decision.completed_at,
        persistence_root=persistence_root,
        portfolio_id=PORTFOLIO_ID,
    )

    assert entry_result.cycle_status == "COMPLETED"
    assert entry_result.terminal_stage == "PERSISTENCE"
    assert entry_result.paper_actions == (
        "OPEN_POSITION",
    )
    assert (
        entry_result.metadata["lifecycle_status"]
        == "OPEN"
    )
    assert entry_result.execution_mode == "PAPER"
    assert (
        entry_result.live_execution_eligible
        is False
    )

    restarted_portfolio, restarted_trade = (
        _restart_services(
            persistence_root
        )
    )

    (
        restarted_ledger,
        restarted_context,
        restarted_binding,
        restarted_observations,
    ) = _restart_task9_stores(
        tmp_path
    )

    binding_values = restarted_binding.by_prediction(
        harness.selected_prediction.prediction_id
    )

    assert binding_values is not None

    paper_trade_id = (
        binding_values.paper_trade_id
    )

    recovered = restarted_trade.get(
        paper_trade_id
    )

    assert recovered is not None
    assert recovered.position is not None
    assert (
        recovered.position.entry_fill
        is not None
    )
    assert (
        recovered.position.exit_fills
        == ()
    )
    assert recovered.latest_observation is not None
    assert (
        recovered.position.entry_fill.observation_id
        == recovered.latest_observation.observation_id
    )

    persisted_portfolio = (
        restarted_portfolio.get(
            PORTFOLIO_ID
        )
    )

    assert persisted_portfolio is not None

    policy_store = _restart_policy_store(
        tmp_path
    )

    portfolio_policy = policy_store.recover(
        persisted_portfolio
        .portfolio_snapshot
        .portfolio_policy_id
    )

    assert portfolio_policy is not None
    assert (
        portfolio_policy.portfolio_policy_id
        == persisted_portfolio
        .portfolio_snapshot
        .portfolio_policy_id
    )
    assert (
        portfolio_policy.execution_mode
        == "PAPER"
    )
    assert (
        portfolio_policy.live_execution_eligible
        is False
    )

    prior = recovered.latest_observation

    assert prior is not None

    observed_at = (
        prior.observed_at
        + timedelta(seconds=1)
    )

    assert (
        recovered.position.target_1_lot_count,
        recovered.position.target_2_lot_count,
        recovered.position.target_3_lot_count,
        recovered.position.runner_lot_count,
    ) == (
        0,
        1,
        0,
        0,
    )

    allocated_target_price = (
        recovered.position.target_2
    )

    allocated_target_observation = replace(
        prior,
        observation_id=(
            "task916-monitor-observation-t2"
        ),
        observed_at=observed_at,
        received_at=observed_at,
        option_last_price=allocated_target_price,
        option_open=allocated_target_price,
        option_low=allocated_target_price,
        option_high=allocated_target_price,
        option_close=allocated_target_price,
    )

    kwargs = _monitor_kwargs(
        portfolio_service=(
            restarted_portfolio
        ),
        trade_service=restarted_trade,
        portfolio_policy=portfolio_policy,
        paper_trade_id=paper_trade_id,
        observation=allocated_target_observation,
    )

    assert (
        kwargs["observation"]
        is allocated_target_observation
    )

    result = execute_task9_position_monitoring(
        recovered_snapshot=recovered,
        observation=allocated_target_observation,
        prediction_ledger=restarted_ledger,
        binding_store=restarted_binding,
        lifecycle_context_store=(
            restarted_context
        ),
        observation_store=(
            restarted_observations
        ),
        monitor=(
            execute_continuous_position_monitoring
        ),
        monitor_kwargs=kwargs,
    )

    assert (
        result.paper_trade_id
        == paper_trade_id
    )
    assert (
        result.prediction_id
        == harness
        .selected_prediction
        .prediction_id
    )
    assert (
        result.monitoring_status
        == "CLOSED"
    )
    assert (
        result.newly_persisted_fill_reasons
        == ("TARGET_2",)
    )
    assert len(
        result.recorded_observation_ids
    ) == 1

    persisted_after = (
        restarted_trade.get(
            paper_trade_id
        )
    )

    assert persisted_after is not None
    assert persisted_after.position is not None

    assert len(
        persisted_after
        .position
        .exit_fills
    ) == 1

    assert (
        persisted_after.position.lifecycle_state
        == "CLOSED_TARGET_2"
    )

    assert (
        persisted_after.position.remaining_quantity
        == 0
    )

    assert (
        persisted_after.position.remaining_lot_count
        == 0
    )

    assert (
        persisted_after
        .position
        .exit_fills[0]
        .fill_reason
        == "TARGET_2"
    )

    # Second process-style restart.
    (
        final_ledger,
        final_context,
        final_binding,
        final_observations,
    ) = _restart_task9_stores(
        tmp_path
    )

    assert (
        final_ledger.recover(
            harness
            .selected_prediction
            .prediction_id
        )
        == harness.selected_prediction
    )

    assert (
        final_context.recover(
            harness
            .selected_prediction
            .prediction_id
        )
        is not None
    )

    assert (
        final_binding.by_trade(
            paper_trade_id
        )
        is not None
    )

    final_policy_store = (
        _restart_policy_store(
            tmp_path
        )
    )

    final_policy = (
        final_policy_store.recover(
            portfolio_policy
            .portfolio_policy_id
        )
    )

    assert final_policy is not None
    assert final_policy == portfolio_policy

    final_portfolio, final_trade = (
        _restart_services(
            persistence_root
        )
    )

    terminal_trade = final_trade.get(
        paper_trade_id
    )

    assert terminal_trade is not None
    assert terminal_trade.position is not None
    assert (
        terminal_trade.position.lifecycle_state
        == "CLOSED_TARGET_2"
    )
    assert (
        terminal_trade.position.remaining_quantity
        == 0
    )
    assert (
        terminal_trade.position.exit_fills[0].fill_reason
        == "TARGET_2"
    )

    terminal_portfolio = final_portfolio.get(
        PORTFOLIO_ID
    )

    assert terminal_portfolio is not None

    assert (
        terminal_portfolio
        .portfolio_snapshot
        .portfolio_policy_id
        == portfolio_policy.portfolio_policy_id
    )

    # Durable Task9 observation file must contain
    # authoritative ENTRY and allocated T2 evidence.
    text = (
        tmp_path
        / "task916-observations.json"
    ).read_text(
        encoding="utf-8"
    )

    entry_source_observation_id = (
        recovered
        .position
        .entry_fill
        .observation_id
    )

    assert entry_source_observation_id in text
    assert (
        allocated_target_observation
        .observation_id
        in text
    )
    assert '"ENTRY"' in text
    assert '"TERMINAL_T2"' in text
    assert final_observations is not None