from __future__ import annotations

from dataclasses import replace

import pytest

from services.certification.task9_position_monitoring_runtime import (
    execute_task9_position_monitoring,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    execute_task9_selected_market_lifecycle,
)
from tests.test_task9_position_monitoring_runtime import (
    PORTFOLIO_ID,
    _restart_services,
    _restart_task9_stores,
)
from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)


def _open_restarted_task9_runtime(tmp_path):
    harness = build_task916_real_runtime_harness(
        tmp_path,
        market="NIFTY",
    )

    persistence_root = (
        tmp_path
        / "task916-runtime"
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
        selected_cycle=harness.selected_cycle,
        selected_planning=harness.selected_planning,
        available_capital=300000.0,
        evaluated_at=harness.decision.completed_at,
        persistence_root=persistence_root,
        portfolio_id=PORTFOLIO_ID,
    )

    assert entry_result.cycle_status == "COMPLETED"
    assert entry_result.paper_actions == (
        "OPEN_POSITION",
    )

    _, trade_service = _restart_services(
        persistence_root
    )

    (
        prediction_ledger,
        lifecycle_context_store,
        binding_store,
        observation_store,
    ) = _restart_task9_stores(
        tmp_path
    )

    binding = binding_store.by_prediction(
        harness.selected_prediction.prediction_id
    )

    assert binding is not None

    recovered = trade_service.get(
        binding.paper_trade_id
    )

    assert recovered is not None
    assert recovered.position is not None
    assert recovered.latest_observation is not None

    return (
        harness,
        recovered,
        prediction_ledger,
        lifecycle_context_store,
        binding_store,
        observation_store,
    )


def test_task9_monitor_rejects_equal_but_distinct_observation_before_monitor(
    tmp_path,
):
    (
        _,
        recovered,
        prediction_ledger,
        lifecycle_context_store,
        binding_store,
        observation_store,
    ) = _open_restarted_task9_runtime(
        tmp_path
    )

    observation = replace(
        recovered.latest_observation,
        observation_id=(
            "task916-exact-object-observation"
        ),
    )

    equal_but_distinct = replace(
        observation
    )

    assert equal_but_distinct == observation
    assert equal_but_distinct is not observation

    monitor_called = False

    def monitor(**kwargs):
        nonlocal monitor_called
        monitor_called = True
        raise AssertionError(
            "monitor must not run after observation identity mismatch"
        )

    with pytest.raises(
        ValueError,
        match=(
            "Task 9 monitor must receive "
            "the exact supplied observation"
        ),
    ):
        execute_task9_position_monitoring(
            recovered_snapshot=recovered,
            observation=observation,
            prediction_ledger=prediction_ledger,
            binding_store=binding_store,
            lifecycle_context_store=(
                lifecycle_context_store
            ),
            observation_store=observation_store,
            monitor=monitor,
            monitor_kwargs={
                "observation": equal_but_distinct,
            },
        )

    assert monitor_called is False


def test_task9_entry_observation_is_idempotent_across_restart(
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

    first = execute_task9_selected_market_lifecycle(
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
        selected_cycle=harness.selected_cycle,
        selected_planning=harness.selected_planning,
        available_capital=300000.0,
        evaluated_at=harness.decision.completed_at,
        persistence_root=persistence_root,
        portfolio_id=PORTFOLIO_ID,
    )

    assert first.cycle_status == "COMPLETED"
    assert first.paper_actions == (
        "OPEN_POSITION",
    )

    observation_path = (
        tmp_path
        / "task916-observations.json"
    )

    before = observation_path.read_text(
        encoding="utf-8"
    )

    (
        restarted_ledger,
        restarted_context,
        restarted_binding,
        restarted_observations,
    ) = _restart_task9_stores(
        tmp_path
    )

    binding = restarted_binding.by_prediction(
        harness.selected_prediction.prediction_id
    )

    assert binding is not None

    recovered_prediction = (
        restarted_ledger.recover(
            harness.selected_prediction.prediction_id
        )
    )

    recovered_context = (
        restarted_context.recover(
            harness.selected_prediction.prediction_id
        )
    )

    assert recovered_prediction is not None
    assert recovered_context is not None

    # Reopening the store itself must not mutate,
    # duplicate, or renumber existing durable evidence.
    after_restart = observation_path.read_text(
        encoding="utf-8"
    )

    assert after_restart == before

    # A second fresh store must decode the same evidence
    # without writing another observation.
    second_restart = type(
        restarted_observations
    )(
        observation_path
    )

    assert second_restart is not None

    after_second_restart = observation_path.read_text(
        encoding="utf-8"
    )

    assert after_second_restart == before

    assert before.count('"event_type":"ENTRY"') == 1