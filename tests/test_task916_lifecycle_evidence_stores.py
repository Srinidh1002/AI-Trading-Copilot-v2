from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.contracts.prediction_lifecycle_outcome_input_v1 import (
    PredictionLifecycleOutcomeInputV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import (
    evaluate_prediction_lifecycle_outcome,
)
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import (
    reconcile_prediction_lifecycle,
)
from services.prediction_outcomes.prediction_observation_window_tracker import (
    build_prediction_observation_window,
)

from tests.test_r77_prediction_lifecycle_outcome_evaluator import (
    obs,
)
from tests.test_task916_prediction_lifecycle_timing_policy import (
    prediction,
)


def _outcome():
    record = prediction("CALL")

    observations = (
        obs(
            record,
            1,
            30,
            "ENTRY",
            option=100.0,
        ),
        obs(
            record,
            2,
            90,
            "STOP",
            option=90.0,
        ),
    )

    window = build_prediction_observation_window(
        prediction=record,
        observations=observations,
        entry_window_ends_at=(
            record.completed_at
            + timedelta(minutes=5)
        ),
        validity_window_ends_at=(
            record.completed_at
            + timedelta(minutes=15)
        ),
    )

    outcome = evaluate_prediction_lifecycle_outcome(
        PredictionLifecycleOutcomeInputV1(
            prediction=record,
            observation_window=window,
            policy=PredictionLifecycleOutcomePolicyV1(
                policy_id="task9-lifecycle-policy",
                policy_version="1.0",
            ),
            evaluated_at=(
                record.completed_at
                + timedelta(minutes=15)
            ),
        )
    )

    return record, outcome


def test_outcome_store_recovers_exact_record_after_restart(
    tmp_path,
):
    _, outcome = _outcome()
    path = tmp_path / "outcomes.json"

    store = Task9PredictionLifecycleOutcomeStore(
        path
    )

    assert store.save(outcome) == "SAVED"

    restarted = Task9PredictionLifecycleOutcomeStore(
        path
    )

    assert (
        restarted.recover(
            outcome.prediction_id
        )
        == outcome
    )

    assert (
        restarted.by_outcome(
            outcome.outcome_id
        )
        == outcome
    )


def test_outcome_store_is_idempotent_and_rejects_conflict(
    tmp_path,
):
    _, outcome = _outcome()
    path = tmp_path / "outcomes.json"

    store = Task9PredictionLifecycleOutcomeStore(
        path
    )

    assert store.save(outcome) == "SAVED"

    assert (
        store.save(outcome)
        == "DUPLICATE_SAME_PAYLOAD"
    )

    conflict = replace(
        outcome,
        warnings=("CONFLICT",),
    )

    with pytest.raises(
        ValueError,
        match="conflicting",
    ):
        store.save(conflict)


def test_outcome_store_corruption_fails_closed(
    tmp_path,
):
    path = tmp_path / "outcomes.json"
    path.write_text(
        '{"version":999}',
        encoding="utf-8",
    )

    store = Task9PredictionLifecycleOutcomeStore(
        path
    )

    with pytest.raises(
        ValueError,
        match="invalid Task 9 lifecycle outcome store",
    ):
        store.recover("prediction")


def test_reconciliation_store_recovers_exact_record_after_restart(
    tmp_path,
):
    record, outcome = _outcome()

    # No-position directional reconciliation is sufficient here to
    # exercise exact durable reconstruction; production terminal
    # position reconciliation is certified separately.
    reconciliation = reconcile_prediction_lifecycle(
        prediction=record,
        outcome=outcome,
        position=None,
        reconciled_at=outcome.evaluated_at,
    )

    path = tmp_path / "reconciliations.json"

    store = (
        Task9PredictionLifecycleReconciliationStore(
            path
        )
    )

    assert (
        store.save(reconciliation)
        == "SAVED"
    )

    restarted = (
        Task9PredictionLifecycleReconciliationStore(
            path
        )
    )

    assert (
        restarted.recover(
            reconciliation.prediction_id
        )
        == reconciliation
    )

    assert (
        restarted.by_reconciliation(
            reconciliation.reconciliation_id
        )
        == reconciliation
    )


def test_reconciliation_store_is_idempotent_and_rejects_conflict(
    tmp_path,
):
    record, outcome = _outcome()

    reconciliation = reconcile_prediction_lifecycle(
        prediction=record,
        outcome=outcome,
        position=None,
        reconciled_at=outcome.evaluated_at,
    )

    path = tmp_path / "reconciliations.json"

    store = (
        Task9PredictionLifecycleReconciliationStore(
            path
        )
    )

    assert store.save(reconciliation) == "SAVED"

    assert (
        store.save(reconciliation)
        == "DUPLICATE_SAME_PAYLOAD"
    )

    conflict = replace(
        reconciliation,
        warnings=("CONFLICT",),
    )

    with pytest.raises(
        ValueError,
        match="conflicting",
    ):
        store.save(conflict)


def test_reconciliation_store_corruption_fails_closed(
    tmp_path,
):
    path = tmp_path / "reconciliations.json"
    path.write_text(
        '{"version":999}',
        encoding="utf-8",
    )

    store = (
        Task9PredictionLifecycleReconciliationStore(
            path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "invalid Task 9 lifecycle reconciliation store"
        ),
    ):
        store.recover("prediction")
