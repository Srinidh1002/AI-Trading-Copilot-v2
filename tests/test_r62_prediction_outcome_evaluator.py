from dataclasses import replace
from datetime import timedelta

import pytest

from services.contracts.prediction_outcome_evaluation_input_v1 import (
    PredictionOutcomeEvaluationInputV1,
)
from services.paper_orchestration.prediction_outcome_evaluator import (
    build_unevaluable_prediction_outcome,
    evaluate_prediction_outcome,
)
from test_r51_prediction_record_v1 import (
    record,
)


def evaluation_input(
    prediction=None,
    *,
    start=25000.0,
    end=25100.0,
    threshold=0.20,
):
    prediction = prediction or record()
    due = (
        prediction.completed_at
        + timedelta(minutes=15)
    )
    return PredictionOutcomeEvaluationInputV1(
        prediction=prediction,
        evaluation_observation_id="evaluation-observation-1",
        start_underlying_price=start,
        end_underlying_price=end,
        evaluation_due_at=due,
        evaluated_at=due,
        evaluation_horizon_seconds=900.0,
        threshold_percent=threshold,
    )


def test_call_up_is_correct_and_call_down_is_incorrect():
    correct = evaluate_prediction_outcome(
        evaluation_input(
            start=25000.0,
            end=25100.0,
        )
    )
    incorrect = evaluate_prediction_outcome(
        evaluation_input(
            start=25000.0,
            end=24900.0,
        )
    )

    assert correct.outcome == "CORRECT"
    assert incorrect.outcome == "INCORRECT"


def test_put_down_is_correct_and_put_up_is_incorrect():
    put = replace(
        record(),
        predicted_direction="BEARISH",
        predicted_action="PUT",
    )

    correct = evaluate_prediction_outcome(
        evaluation_input(
            put,
            start=25000.0,
            end=24900.0,
        )
    )
    incorrect = evaluate_prediction_outcome(
        evaluation_input(
            put,
            start=25000.0,
            end=25100.0,
        )
    )

    assert correct.outcome == "CORRECT"
    assert incorrect.outcome == "INCORRECT"


def test_directional_move_below_threshold_is_flat():
    result = evaluate_prediction_outcome(
        evaluation_input(
            start=25000.0,
            end=25010.0,
            threshold=0.20,
        )
    )

    assert result.outcome == "FLAT"


def test_wait_evaluates_good_wait_neutral_and_missed_opportunity():
    wait = replace(
        record(),
        predicted_action="WAIT",
        parent_selected=False,
        outcome_reason="LOWER_RANK",
    )

    good = evaluate_prediction_outcome(
        evaluation_input(
            wait,
            start=25000.0,
            end=25010.0,
            threshold=0.20,
        )
    )
    neutral = evaluate_prediction_outcome(
        evaluation_input(
            wait,
            start=25000.0,
            end=25050.0,
            threshold=0.20,
        )
    )
    missed = evaluate_prediction_outcome(
        evaluation_input(
            wait,
            start=25000.0,
            end=25100.0,
            threshold=0.20,
        )
    )

    assert good.outcome == "GOOD_WAIT"
    assert neutral.outcome == "NEUTRAL_WAIT"
    assert missed.outcome == "MISSED_OPPORTUNITY"


def test_input_rejects_horizon_mismatch_and_early_evaluation():
    value = evaluation_input()

    with pytest.raises(
        ValueError,
        match="horizon",
    ):
        replace(
            value,
            evaluation_horizon_seconds=60.0,
        )

    with pytest.raises(
        ValueError,
        match="evaluated_at",
    ):
        replace(
            value,
            evaluated_at=(
                value.evaluation_due_at
                - timedelta(seconds=1)
            ),
        )


def test_unevaluable_outcome_is_explicit():
    prediction = record()
    due = (
        prediction.completed_at
        + timedelta(minutes=15)
    )

    result = build_unevaluable_prediction_outcome(
        prediction=prediction,
        evaluation_due_at=due,
        evaluated_at=due,
        evaluation_horizon_seconds=900.0,
        threshold_percent=0.20,
        blocker="EVALUATION_PRICE_UNAVAILABLE",
    )

    assert result.evaluation_status == "UNEVALUABLE"
    assert result.outcome == "UNEVALUABLE"
    assert result.blockers == (
        "EVALUATION_PRICE_UNAVAILABLE",
    )
