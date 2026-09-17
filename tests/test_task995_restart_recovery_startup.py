"""Task 9.95B deterministic production restart/startup recovery."""

from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import timedelta

import pytest

import services.certification.task9_live_paper_certification_launcher as launcher_module

from services.certification.task9_abstention_later_observation_recovery import (
    recover_task9_later_abstention_observations,
)
from services.certification.task9_live_paper_production_composition import (
    Task9ProductionPersistenceLayoutV1,
)
from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_position_monitoring_runtime import (
    execute_task9_position_monitoring,
)
from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_restart_recovery_startup import (
    run_task9_restart_recovery_startup,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    execute_task9_selected_market_lifecycle,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.paper_orchestration.continuous_position_monitoring_runtime import (
    execute_continuous_position_monitoring,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)

from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)
from tests.test_task916_live_paper_certification_launcher import (
    _launcher,
)
from tests.test_task916_production_child_evidence_authority import (
    _quote,
    _runtime,
)
from tests.test_task9_position_monitoring_runtime import (
    PORTFOLIO_ID,
    _monitor_kwargs,
    _restart_policy_store,
    _restart_services,
    _restart_task9_stores,
)


PRODUCTION_POLICY = PredictionLifecycleOutcomePolicyV1(
    policy_id="task9-production-lifecycle-policy",
    policy_version="1.0",
)


def _copy_file(source, destination):
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    shutil.copyfile(
        source,
        destination,
    )


def _paper_only(result):
    assert result.execution_mode == "PAPER"
    assert result.broker_order_submission is False
    assert result.live_execution_eligible is False


def _seed_canonical_abstentions(root, seed):
    layout = (
        Task9ProductionPersistenceLayoutV1
        .from_root(root)
    )

    ledger = PredictionLedger(
        layout.prediction_ledger_path
    )

    predictions = tuple(
        seed["predictions"]
    )

    assert len(predictions) == 2

    ledger.save_pair(
        predictions
    )

    context_store = (
        Task9PredictionLifecycleContextStore(
            layout.lifecycle_context_store_path
        )
    )

    observation_store = (
        Task9PredictionObservationWindowStore(
            layout.observation_window_store_path
        )
    )

    outcome_store = (
        Task9PredictionLifecycleOutcomeStore(
            layout.lifecycle_outcome_store_path
        )
    )

    contexts = []

    for prediction in predictions:
        source_context = (
            seed["context_store"].recover(
                prediction.prediction_id
            )
        )

        assert source_context is not None

        assert (
            context_store.save(
                source_context
            )
            == "SAVED"
        )

        observation_store.initialize(
            prediction=prediction,
            entry_window_ends_at=(
                source_context
                .entry_window_ends_at
            ),
            validity_window_ends_at=(
                source_context
                .validity_window_ends_at
            ),
        )

        quote, quality = _quote(
            prediction
        )

        recover_task9_later_abstention_observations(
            market=prediction.underlying_symbol,
            exchange=prediction.exchange,
            quote=quote,
            data_quality=quality,
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
            outcome_store=outcome_store,
            outcome_policy=PRODUCTION_POLICY,
            evaluated_at=quote.observed_at,
        )

        contexts.append(
            source_context
        )

    return (
        layout,
        predictions,
        tuple(contexts),
    )


def _build_real_terminal_seed(tmp_path):
    seed_root = (
        tmp_path
        / "terminal-seed"
    )

    harness = (
        build_task916_real_runtime_harness(
            seed_root,
            market="NIFTY",
        )
    )

    persistence_root = (
        tmp_path
        / "terminal-paper-runtime"
    )

    portfolio_policy_store = (
        Task9PaperPortfolioPolicyStore(
            seed_root
            / "task916-portfolio-policies.json"
        )
    )

    entry = (
        execute_task9_selected_market_lifecycle(
            official_run_id=(
                "task916-official-run"
            ),
            binding_store=(
                harness.binding_store
            ),
            prediction_id=(
                harness
                .selected_prediction
                .prediction_id
            ),
            prediction_ledger=(
                harness.prediction_ledger
            ),
            lifecycle_context_store=(
                harness.lifecycle_context_store
            ),
            observation_store=(
                harness.observation_store
            ),
            portfolio_policy_store=(
                portfolio_policy_store
            ),
            selected_cycle=(
                harness.selected_cycle
            ),
            selected_planning=(
                harness.selected_planning
            ),
            available_capital=300000.0,
            evaluated_at=(
                harness.decision.completed_at
            ),
            persistence_root=(
                persistence_root
            ),
            portfolio_id=PORTFOLIO_ID,
        )
    )

    assert entry.cycle_status == "COMPLETED"

    (
        portfolio_service,
        trade_service,
    ) = _restart_services(
        persistence_root
    )

    (
        ledger,
        context_store,
        binding_store,
        observation_store,
    ) = _restart_task9_stores(
        seed_root
    )

    binding = (
        binding_store.by_prediction(
            harness
            .selected_prediction
            .prediction_id
        )
    )

    assert binding is not None

    snapshot = trade_service.get(
        binding.paper_trade_id
    )

    assert snapshot is not None
    assert snapshot.position is not None
    assert snapshot.latest_observation is not None

    portfolio_snapshot = (
        portfolio_service.get(
            PORTFOLIO_ID
        )
    )

    assert portfolio_snapshot is not None

    policy = (
        _restart_policy_store(
            seed_root
        ).recover(
            portfolio_snapshot
            .portfolio_snapshot
            .portfolio_policy_id
        )
    )

    assert policy is not None

    prior = snapshot.latest_observation

    observed_at = (
        prior.observed_at
        + timedelta(seconds=1)
    )

    target_price = (
        snapshot.position.target_2
    )

    terminal_observation = replace(
        prior,
        observation_id=(
            "task995-terminal-t2"
        ),
        observed_at=observed_at,
        received_at=observed_at,
        option_last_price=target_price,
        option_open=target_price,
        option_low=target_price,
        option_high=target_price,
        option_close=target_price,
    )

    kwargs = _monitor_kwargs(
        portfolio_service=(
            portfolio_service
        ),
        trade_service=trade_service,
        portfolio_policy=policy,
        paper_trade_id=(
            binding.paper_trade_id
        ),
        observation=(
            terminal_observation
        ),
    )

    monitoring = (
        execute_task9_position_monitoring(
            recovered_snapshot=snapshot,
            observation=(
                terminal_observation
            ),
            prediction_ledger=ledger,
            binding_store=binding_store,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
            monitor=(
                execute_continuous_position_monitoring
            ),
            monitor_kwargs=kwargs,
        )
    )

    assert (
        monitoring.monitoring_status
        == "CLOSED"
    )

    terminal_snapshot = trade_service.get(
        binding.paper_trade_id
    )

    assert terminal_snapshot is not None
    assert terminal_snapshot.position is not None
    assert (
        terminal_snapshot
        .lifecycle_state
        .is_terminal
        is True
    )

    assert (
        terminal_snapshot
        .position
        .lifecycle_state
        == "CLOSED_TARGET_2"
    )

    return {
        "seed_root": seed_root,
        "paper_root": persistence_root,
        "harness": harness,
        "binding": binding,
        "terminal_snapshot": (
            terminal_snapshot
        ),
        "evaluated_at": observed_at,
    }


def _copy_terminal_seed_to_canonical(
    *,
    seed,
    canonical_root,
):
    layout = (
        Task9ProductionPersistenceLayoutV1
        .from_root(canonical_root)
    )

    seed_root = seed["seed_root"]
    paper_root = seed["paper_root"]

    _copy_file(
        seed_root
        / "task916-prediction-ledger.json",
        layout.prediction_ledger_path,
    )

    _copy_file(
        seed_root
        / "task916-lifecycle-context.json",
        layout.lifecycle_context_store_path,
    )

    _copy_file(
        seed_root
        / "task916-observations.json",
        layout.observation_window_store_path,
    )

    _copy_file(
        seed_root
        / "task916-bindings.json",
        layout.binding_store_path,
    )

    _copy_file(
        paper_root
        / "p7_trades.json",
        layout.paper_trade_repository_path,
    )

    _copy_file(
        paper_root
        / "p8_portfolios.json",
        layout.paper_portfolio_repository_path,
    )

    return layout


def test_empty_restart_is_safe_noop(
    tmp_path,
):
    root = tmp_path / "task9"

    result = (
        run_task9_restart_recovery_startup(
            official_run_id="task995-empty",
            official_start_at=(
                _runtime(
                    tmp_path / "clock-seed",
                    nifty_action="WAIT",
                    sensex_action="NO_TRADE",
                )["boundary"]
            ),
            persistence_root=root,
            evaluated_at=(
                _runtime(
                    tmp_path / "clock-seed-2",
                    nifty_action="WAIT",
                    sensex_action="NO_TRADE",
                )["boundary"]
            ),
            starting_capital=300000.0,
            run_classification=(
                "OFFICIAL_CERTIFICATION"
            ),
        )
    )

    assert result == ()


def test_expired_wait_no_trade_restart_completes_analytics_and_is_idempotent(
    tmp_path,
):
    seed = _runtime(
        tmp_path / "abstention-seed",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )

    root = tmp_path / "task9"

    (
        layout,
        predictions,
        contexts,
    ) = _seed_canonical_abstentions(
        root,
        seed,
    )

    boundary = (
        max(
            context.validity_window_ends_at
            for context in contexts
        )
        + timedelta(seconds=1)
    )

    first = (
        run_task9_restart_recovery_startup(
            official_run_id=(
                "task995-abstention-run"
            ),
            official_start_at=(
                seed["boundary"]
            ),
            persistence_root=root,
            evaluated_at=boundary,
            starting_capital=300000.0,
            run_classification=(
                "OFFICIAL_CERTIFICATION"
            ),
        )
    )

    assert tuple(
        item.prediction_id
        for item in first
    ) == tuple(
        sorted(
            prediction.prediction_id
            for prediction in predictions
        )
    )

    assert {
        item.status
        for item in first
    } == {
        "ALREADY_COMPLETE"
    }

    for item in first:
        _paper_only(item)

    outcome_store = (
        Task9PredictionLifecycleOutcomeStore(
            layout.lifecycle_outcome_store_path
        )
    )

    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            layout.lifecycle_reconciliation_store_path
        )
    )

    first_outcomes = {}
    first_reconciliations = {}

    for prediction in predictions:
        outcome = outcome_store.recover(
            prediction.prediction_id
        )
        reconciliation = (
            reconciliation_store.recover(
                prediction.prediction_id
            )
        )

        assert outcome is not None
        assert reconciliation is not None

        assert (
            outcome.entry_occurred
            is False
        )

        assert (
            reconciliation.position_id
            is None
        )

        assert (
            reconciliation.status
            == "RECONCILED"
        )

        first_outcomes[
            prediction.prediction_id
        ] = outcome

        first_reconciliations[
            prediction.prediction_id
        ] = reconciliation

    second = (
        run_task9_restart_recovery_startup(
            official_run_id=(
                "task995-abstention-run"
            ),
            official_start_at=(
                seed["boundary"]
            ),
            persistence_root=root,
            evaluated_at=boundary,
            starting_capital=300000.0,
            run_classification=(
                "OFFICIAL_CERTIFICATION"
            ),
        )
    )

    assert second == first

    for prediction in predictions:
        assert (
            outcome_store.recover(
                prediction.prediction_id
            )
            == first_outcomes[
                prediction.prediction_id
            ]
        )

        assert (
            reconciliation_store.recover(
                prediction.prediction_id
            )
            == first_reconciliations[
                prediction.prediction_id
            ]
        )


def test_terminal_directional_restart_recovers_from_durable_facts_without_provider(
    tmp_path,
):
    seed = _build_real_terminal_seed(
        tmp_path
    )

    root = tmp_path / "task9"

    layout = (
        _copy_terminal_seed_to_canonical(
            seed=seed,
            canonical_root=root,
        )
    )

    prediction_id = (
        seed["harness"]
        .selected_prediction
        .prediction_id
    )

    outcome_store = (
        Task9PredictionLifecycleOutcomeStore(
            layout.lifecycle_outcome_store_path
        )
    )

    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            layout.lifecycle_reconciliation_store_path
        )
    )

    assert (
        outcome_store.recover(
            prediction_id
        )
        is None
    )

    assert (
        reconciliation_store.recover(
            prediction_id
        )
        is None
    )

    first = (
        run_task9_restart_recovery_startup(
            official_run_id=(
                "task916-official-run"
            ),
            official_start_at=(
                seed["harness"]
                .decision
                .completed_at
            ),
            persistence_root=root,
            evaluated_at=(
                seed["evaluated_at"]
            ),
            starting_capital=300000.0,
            run_classification=(
                "OFFICIAL_CERTIFICATION"
            ),
        )
    )

    selected_result = next(
        item
        for item in first
        if item.prediction_id
        == prediction_id
    )

    # Final pass sees the recovered terminal
    # lifecycle as complete.
    assert (
        selected_result.status
        == "ALREADY_COMPLETE"
    )

    _paper_only(
        selected_result
    )

    outcome = outcome_store.recover(
        prediction_id
    )

    reconciliation = (
        reconciliation_store.recover(
            prediction_id
        )
    )

    assert outcome is not None
    assert reconciliation is not None

    assert (
        reconciliation.status
        == "RECONCILED"
    )

    assert (
        reconciliation
        .reconciliation_complete
        is True
    )

    assert (
        reconciliation.position_id
        == seed["binding"]
        .paper_position_id
    )

    first_outcome = outcome
    first_reconciliation = reconciliation

    second = (
        run_task9_restart_recovery_startup(
            official_run_id=(
                "task916-official-run"
            ),
            official_start_at=(
                seed["harness"]
                .decision
                .completed_at
            ),
            persistence_root=root,
            evaluated_at=(
                seed["evaluated_at"]
            ),
            starting_capital=300000.0,
            run_classification=(
                "OFFICIAL_CERTIFICATION"
            ),
        )
    )

    second_selected = next(
        item
        for item in second
        if item.prediction_id
        == prediction_id
    )

    assert (
        second_selected.status
        == "ALREADY_COMPLETE"
    )

    assert (
        outcome_store.recover(
            prediction_id
        )
        == first_outcome
    )

    assert (
        reconciliation_store.recover(
            prediction_id
        )
        == first_reconciliation
    )


def test_launcher_runs_restart_recovery_before_first_fresh_parent_cycle(
    tmp_path,
    monkeypatch,
):
    now = _runtime(
        tmp_path / "launcher-seed",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )["boundary"]

    events = []

    def startup_recovery(**kwargs):
        events.append(
            (
                "recovery",
                kwargs["official_run_id"],
            )
        )
        return ()

    monkeypatch.setattr(
        launcher_module,
        "run_task9_restart_recovery_startup",
        startup_recovery,
    )

    def task8_factory(
        *,
        task9_cycle_evidence_sink,
    ):
        def parent_cycle():
            events.append(
                (
                    "parent",
                    "fresh-evidence",
                )
            )
            raise RuntimeError(
                "TASK995_PARENT_REACHED"
            )

        return type(
            "Task8Dependencies",
            (),
            {
                "execution_mode": "PAPER",
                "broker_order_submission": False,
                "live_execution_eligible": False,
                "parent_cycle": staticmethod(
                    parent_cycle
                ),
                "selected_planner": staticmethod(
                    lambda _: None
                ),
            },
        )()

    launcher = _launcher(
        tmp_path,
        task9_evidence_factory=task8_factory,
        runtime_factory=(
            lambda **_: pytest.fail(
                "runtime must not build "
                "after parent sentinel"
            )
        ),
        now=now,
    )

    with pytest.raises(
        RuntimeError,
        match="TASK995_PARENT_REACHED",
    ):
        launcher.run(
            max_cycles=1
        )

    assert events == [
        (
            "recovery",
            "task9-live-operator-run",
        ),
        (
            "parent",
            "fresh-evidence",
        ),
    ]

    assert not (
        tmp_path
        / "task9"
        / "task9-live-paper.lock"
    ).exists()

