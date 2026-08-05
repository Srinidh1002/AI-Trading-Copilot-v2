from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.prediction_outcome_record_v1 import (
    PredictionOutcomeRecordV1,
)


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)


def directional(**changes):
    start = 25000.0
    end = 25100.0
    movement = end - start
    percent = movement / start * 100.0

    values = dict(
        outcome_id="outcome:prediction-1",
        prediction_id="prediction-1",
        parent_cycle_id="parent-1",
        decision_result_id="decision-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        predicted_action="CALL",
        evaluation_kind="DIRECTIONAL",
        prediction_completed_at=NOW,
        evaluation_due_at=NOW + timedelta(minutes=15),
        evaluated_at=NOW + timedelta(minutes=15),
        evaluation_status="EVALUATED",
        outcome="CORRECT",
        start_underlying_price=start,
        end_underlying_price=end,
        movement_points=movement,
        movement_percent=percent,
        absolute_movement_percent=abs(percent),
        evaluation_horizon_seconds=900.0,
        threshold_percent=0.20,
        evidence_observation_id="evaluation-observation-1",
    )
    values.update(changes)
    return PredictionOutcomeRecordV1(**values)


def abstention(**changes):
    start = 80000.0
    end = 80020.0
    movement = end - start
    percent = movement / start * 100.0

    values = dict(
        outcome_id="outcome:prediction-2",
        prediction_id="prediction-2",
        parent_cycle_id="parent-1",
        decision_result_id="decision-1",
        underlying_symbol="SENSEX",
        exchange="BSE",
        predicted_action="WAIT",
        evaluation_kind="ABSTENTION",
        prediction_completed_at=NOW,
        evaluation_due_at=NOW + timedelta(minutes=15),
        evaluated_at=NOW + timedelta(minutes=15),
        evaluation_status="EVALUATED",
        outcome="NEUTRAL_WAIT",
        start_underlying_price=start,
        end_underlying_price=end,
        movement_points=movement,
        movement_percent=percent,
        absolute_movement_percent=abs(percent),
        evaluation_horizon_seconds=900.0,
        threshold_percent=0.20,
        evidence_observation_id="evaluation-observation-2",
    )
    values.update(changes)
    return PredictionOutcomeRecordV1(**values)


def test_directional_record_is_immutable_and_deterministic():
    value = directional()

    assert value.to_json() == directional().to_json()
    assert len(value.semantic_hash) == 64

    with pytest.raises(FrozenInstanceError):
        value.outcome = "INCORRECT"

    with pytest.raises(ValueError):
        replace(value, execution_mode="LIVE")

    with pytest.raises(ValueError):
        replace(value, broker_order_submission=True)


def test_wait_uses_abstention_vocabulary():
    value = abstention()

    assert value.predicted_action == "WAIT"
    assert value.evaluation_kind == "ABSTENTION"

    with pytest.raises(ValueError):
        abstention(evaluation_kind="DIRECTIONAL")

    with pytest.raises(ValueError):
        abstention(outcome="CORRECT")


def test_evaluated_prices_and_movements_must_cohere():
    with pytest.raises(
        ValueError,
        match="movement_points mismatch",
    ):
        directional(movement_points=1.0)

    with pytest.raises(
        ValueError,
        match="both prices",
    ):
        directional(end_underlying_price=None)


def test_unevaluable_record_is_explicit_and_zero_evidence():
    value = directional(
        evaluation_status="UNEVALUABLE",
        outcome="UNEVALUABLE",
        start_underlying_price=None,
        end_underlying_price=None,
        movement_points=None,
        movement_percent=None,
        absolute_movement_percent=None,
        evidence_observation_id=None,
        blockers=("EVALUATION_PRICE_UNAVAILABLE",),
    )

    assert value.outcome == "UNEVALUABLE"

    with pytest.raises(
        ValueError,
        match="requires blocker",
    ):
        replace(value, blockers=())


def test_due_time_must_be_reached_before_evaluation():
    with pytest.raises(
        ValueError,
        match="evaluation_due_at",
    ):
        directional(
            evaluated_at=NOW + timedelta(minutes=5),
        )
