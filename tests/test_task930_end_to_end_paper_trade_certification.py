"""Provider-free Task 9 end-to-end PAPER certification rehearsal."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_certification_publication import (
    Task9CertificationPublicationAuthority,
)
from services.certification.task9_open_position_monitoring_controller import (
    Task9OpenPositionMonitoringController,
)
from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    execute_task9_selected_market_lifecycle,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)
from tests.test_task916_production_child_evidence_authority import _runtime
from tests.test_task9_live_paper_trade_counting_evaluator import (
    lifecycle_outcome,
)
from tests.test_task9_position_monitoring_runtime import _monitor_kwargs


def _rehearsal(tmp_path, market):
    harness = build_task916_real_runtime_harness(
        tmp_path / "seed",
        market=market,
    )

    root = tmp_path / "runtime"
    portfolio_id = f"task930-{market.lower()}-portfolio"

    policy_store = Task9PaperPortfolioPolicyStore(
        tmp_path / "policies.json"
    )

    entry = execute_task9_selected_market_lifecycle(
        official_run_id="task930-rehearsal",
        binding_store=harness.binding_store,
        prediction_id=harness.selected_prediction.prediction_id,
        prediction_ledger=harness.prediction_ledger,
        lifecycle_context_store=harness.lifecycle_context_store,
        observation_store=harness.observation_store,
        portfolio_policy_store=policy_store,
        selected_cycle=harness.selected_cycle,
        selected_planning=harness.selected_planning,
        available_capital=300000.0,
        evaluated_at=harness.decision.completed_at,
        persistence_root=root,
        portfolio_id=portfolio_id,
    )

    assert entry.paper_actions == ("OPEN_POSITION",)
    assert entry.execution_mode == "PAPER"

    binding = harness.binding_store.by_prediction(
        harness.selected_prediction.prediction_id
    )

    assert binding is not None
    assert binding.execution_mode == "PAPER"
    assert binding.broker_order_submission is False
    assert binding.live_execution_eligible is False

    portfolio_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(
            root / "p8_portfolios.json"
        )
    )

    trade_service = PaperTradePersistenceService(
        PaperTradeRepository(
            root / "p7_trades.json"
        )
    )

    snapshot = trade_service.get(
        binding.paper_trade_id
    )

    assert snapshot is not None
    assert snapshot.position is not None
    assert snapshot.lifecycle_state.current_state == "OPEN"

    outcome_store = Task9PredictionLifecycleOutcomeStore(
        tmp_path / "outcomes.json"
    )

    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            tmp_path / "reconciliations.json"
        )
    )

    authority = Task9CertificationPublicationAuthority(
        official_run_id="task930-rehearsal",
        official_start_at=(
            harness.decision.completed_at
            - timedelta(seconds=1)
        ),
        root=tmp_path / "reports",
        prediction_ledger=harness.prediction_ledger,
        binding_store=harness.binding_store,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        trade_persistence_service=trade_service,
        starting_capital=10000.0,
    )

    return (
        harness,
        portfolio_id,
        policy_store,
        portfolio_service,
        trade_service,
        binding,
        snapshot,
        outcome_store,
        reconciliation_store,
        authority,
    )


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_real_paper_entry_terminal_monitoring_reconciliation_and_publication(
    tmp_path,
    market,
):
    (
        harness,
        portfolio_id,
        policy_store,
        portfolio_service,
        trade_service,
        binding,
        snapshot,
        outcomes,
        reconciliations,
        authority,
    ) = _rehearsal(
        tmp_path,
        market,
    )

    before = authority.refresh(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=harness.decision.completed_at,
    )

    current = (
        before.nifty
        if market == "NIFTY"
        else before.sensex
    )

    assert current.completed_live_paper_trades == 0
    assert current.pending_entered_trades == 1

    open_report = authority._build_report(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=harness.decision.completed_at,
    )

    open_fact = next(
        item
        for item in open_report.prediction_facts
        if item.prediction_id == binding.prediction_id
    )

    assert open_report.entry_count == 1
    assert open_fact.entry_occurred is True
    assert open_fact.closed_position is False
    assert open_fact.officially_counted is False
    assert open_fact.counting_status == "PENDING_OUTCOME"

    prior = snapshot.latest_observation
    position = snapshot.position

    assert prior is not None
    assert position is not None

    target = position.target_2

    observation = replace(
        prior,
        observation_id=f"task930-{market}-target",
        observed_at=(
            prior.observed_at
            + timedelta(seconds=1)
        ),
        received_at=(
            prior.received_at
            + timedelta(seconds=1)
        ),
        option_last_price=target,
        option_open=target,
        option_low=target,
        option_high=target,
        option_close=target,
    )

    portfolio_snapshot = portfolio_service.get(
        portfolio_id
    )

    assert portfolio_snapshot is not None

    policy = policy_store.recover(
        portfolio_snapshot
        .portfolio_snapshot
        .portfolio_policy_id
    )

    assert policy is not None

    def monitor_kwargs_factory(**_):
        kwargs = _monitor_kwargs(
            portfolio_service=portfolio_service,
            trade_service=trade_service,
            portfolio_policy=policy,
            paper_trade_id=binding.paper_trade_id,
            observation=observation,
        )

        kwargs["portfolio_id"] = portfolio_id

        return kwargs

    controller = Task9OpenPositionMonitoringController(
        official_run_id="task930-rehearsal",
        portfolio_id=portfolio_id,
        prediction_ledger=harness.prediction_ledger,
        binding_store=harness.binding_store,
        lifecycle_context_store=(
            harness.lifecycle_context_store
        ),
        observation_store=harness.observation_store,
        outcome_store=outcomes,
        reconciliation_store=reconciliations,
        outcome_policy=PredictionLifecycleOutcomePolicyV1(
            policy_id="task930",
            policy_version="1.0",
        ),
        portfolio_persistence_service=portfolio_service,
        trade_persistence_service=trade_service,
        monitor_kwargs_factory=monitor_kwargs_factory,
    )

    result = controller.run_once(
        observation_provider=lambda *_: observation,
        evaluated_at=observation.observed_at,
    )

    assert len(result) == 1
    assert result[0].terminal_reconciled is True

    terminal = trade_service.get(
        binding.paper_trade_id
    )

    assert terminal is not None
    assert terminal.position is not None
    assert (
        terminal.position.lifecycle_state
        == "CLOSED_TARGET_2"
    )
    assert terminal.position.remaining_quantity == 0

    persisted_outcome = outcomes.recover(
        binding.prediction_id
    )
    persisted_reconciliation = reconciliations.recover(
        binding.prediction_id
    )

    assert persisted_outcome is not None
    assert persisted_reconciliation is not None

    assert (
        persisted_outcome.evaluation_status
        == "RESOLVED"
    )
    assert persisted_outcome.outcome == "T2_HIT"
    assert (
        persisted_outcome.terminal_event_type
        == "TERMINAL_T2"
    )
    assert (
        persisted_outcome.terminal_event_at
        == terminal.position.exit_fills[-1].filled_at
    )
    assert (
        persisted_outcome.terminal_option_premium
        == terminal.position.exit_fills[-1].fill_price
    )

    assert (
        persisted_reconciliation.status
        == "RECONCILED"
    )
    assert (
        persisted_reconciliation.reconciliation_complete
        is True
    )
    assert (
        persisted_reconciliation.counting_eligible
        is True
    )
    assert (
        persisted_reconciliation.pnl_matches
        is True
    )

    after = authority.refresh(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=observation.observed_at,
    )

    counted, other = (
        (after.nifty, after.sensex)
        if market == "NIFTY"
        else (after.sensex, after.nifty)
    )

    decision = authority._decision(
        harness.selected_prediction,
        persisted_outcome,
        persisted_reconciliation,
        observation.observed_at,
    )

    terminal_report = authority._build_report(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=observation.observed_at,
    )

    terminal_fact = next(
        item
        for item in terminal_report.prediction_facts
        if item.prediction_id == binding.prediction_id
    )

    assert decision.status == "INCLUDED"
    assert terminal_fact.officially_counted is True

    assert (
        counted.completed_live_paper_trades,
        counted.pending_entered_trades,
        counted.remaining_trade_count,
    ) == (
        1,
        0,
        99,
    )

    assert (
        other.completed_live_paper_trades,
        other.remaining_trade_count,
    ) == (
        0,
        100,
    )

    report = authority._build_report(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=observation.observed_at,
    )

    fact = next(
        item
        for item in report.prediction_facts
        if item.prediction_id == binding.prediction_id
    )

    assert fact.entry_occurred is True
    assert fact.closed_position is True
    assert fact.counting_status == "INCLUDED"
    assert fact.officially_counted is True
    assert fact.lifecycle_status == "RESOLVED"
    assert (
        fact.reconciliation_status
        == "RECONCILED"
    )

    assert len(
        harness.binding_store.list_all()
    ) == 1

    assert controller.run_once(
        observation_provider=lambda *_: observation,
        evaluated_at=observation.observed_at,
    ) == ()

    repeated = authority.refresh(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=observation.observed_at,
    )

    repeated_counted = (
        repeated.nifty
        if market == "NIFTY"
        else repeated.sensex
    )

    assert (
        repeated_counted.completed_live_paper_trades
        == 1
    )
    assert (
        repeated_counted.pending_entered_trades
        == 0
    )

    recovered_authority = (
        Task9CertificationPublicationAuthority(
            official_run_id="task930-rehearsal",
            official_start_at=(
                harness.decision.completed_at
                - timedelta(seconds=1)
            ),
            root=tmp_path / "reports",
            prediction_ledger=PredictionLedger(
                tmp_path
                / "seed"
                / "task916-prediction-ledger.json"
            ),
            binding_store=(
                Task9PredictionPaperTradeBindingStore(
                    tmp_path
                    / "seed"
                    / "task916-bindings.json"
                )
            ),
            outcome_store=(
                Task9PredictionLifecycleOutcomeStore(
                    tmp_path / "outcomes.json"
                )
            ),
            reconciliation_store=(
                Task9PredictionLifecycleReconciliationStore(
                    tmp_path / "reconciliations.json"
                )
            ),
            trade_persistence_service=(
                PaperTradePersistenceService(
                    PaperTradeRepository(
                        tmp_path
                        / "runtime"
                        / "p7_trades.json"
                    )
                )
            ),
            starting_capital=10000.0,
        )
    )

    recovered = recovered_authority.refresh(
        session_date=harness.decision.completed_at.date(),
        evaluated_at=observation.observed_at,
    )

    recovered_counted = (
        recovered.nifty
        if market == "NIFTY"
        else recovered.sensex
    )

    recovered_other = (
        recovered.sensex
        if market == "NIFTY"
        else recovered.nifty
    )

    assert (
        recovered_counted.completed_live_paper_trades
        == 1
    )
    assert (
        recovered_other.completed_live_paper_trades
        == 0
    )


def _publication_authority(
    tmp_path,
    runtime,
):
    official_start_at = (
        min(
            prediction.completed_at
            for prediction in runtime["predictions"]
        )
        - timedelta(seconds=1)
    )

    return Task9CertificationPublicationAuthority(
        official_run_id="task930-rehearsal",
        official_start_at=official_start_at,
        root=tmp_path / "reports",

        # _runtime() returns this authority as "ledger".
        prediction_ledger=runtime["ledger"],

        binding_store=runtime["binding_store"],
        outcome_store=runtime["outcome_store"],
        reconciliation_store=(
            runtime["reconciliation_store"]
        ),
        trade_persistence_service=(
            runtime["trade_service"]
        ),
        starting_capital=10000.0,
    )


def test_call_without_durable_entry_remains_noncounting(
    tmp_path,
):
    runtime = _runtime(
        tmp_path,
        nifty_action="CALL",
        sensex_action="WAIT",
    )

    authority = _publication_authority(
        tmp_path,
        runtime,
    )

    report = authority._build_report(
        session_date=runtime["boundary"].date(),
        evaluated_at=runtime["boundary"],
    )

    call_fact = next(
        item
        for item in report.prediction_facts
        if item.action == "CALL"
    )

    progress = authority.refresh(
        session_date=runtime["boundary"].date(),
        evaluated_at=runtime["boundary"],
    )

    assert call_fact.entry_occurred is False
    assert call_fact.officially_counted is False

    assert (
        progress.nifty.completed_live_paper_trades
        == 0
    )
    assert (
        progress.nifty.pending_entered_trades
        == 0
    )
    assert (
        progress.nifty.remaining_trade_count
        == 100
    )


@pytest.mark.parametrize(
    (
        "action",
        "outcome_name",
        "expected_status",
    ),
    (
        (
            "WAIT",
            "NO_TRADE_CORRECT",
            "INCLUDED_WAIT",
        ),
        (
            "NO_TRADE",
            "NO_TRADE_MISSED_MOVE",
            "INCLUDED_NON_TRADE",
        ),
    ),
)
def test_resolved_abstentions_remain_nontrade_and_never_increment_paper_target(
    tmp_path,
    action,
    outcome_name,
    expected_status,
):
    runtime = _runtime(
        tmp_path,
        nifty_action=action,
        sensex_action="WAIT",
    )

    prediction = runtime["predictions"][0]

    runtime["outcome_store"].save(
        lifecycle_outcome(
            prediction,
            outcome=outcome_name,
            entry_occurred=False,
            entry_at=None,
            entry_premium=None,
            terminal_event_type=(
                "VALIDITY_WINDOW_END"
            ),
            terminal_event_at=runtime["boundary"],
            terminal_option_premium=None,
        )
    )

    authority = _publication_authority(
        tmp_path,
        runtime,
    )

    report = authority._build_report(
        session_date=runtime["boundary"].date(),
        evaluated_at=runtime["boundary"],
    )

    fact = next(
        item
        for item in report.prediction_facts
        if item.prediction_id
        == prediction.prediction_id
    )

    progress = authority.refresh(
        session_date=runtime["boundary"].date(),
        evaluated_at=runtime["boundary"],
    )

    assert fact.counting_status == expected_status
    assert fact.entry_occurred is False
    assert fact.officially_counted is False

    assert (
        progress.nifty.completed_live_paper_trades
        == 0
    )
    assert (
        progress.nifty.pending_entered_trades
        == 0
    )

    assert (
        progress.nifty.no_trade_completed
        == (
            1
            if action == "NO_TRADE"
            else 0
        )
    )