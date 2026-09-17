"""Deterministic CALL/PUT/WAIT prediction outcome authority."""
from __future__ import annotations

from services.contracts.prediction_outcome_evaluation_input_v1 import (
    PredictionOutcomeEvaluationInputV1,
)
from services.contracts.prediction_outcome_record_v1 import (
    PredictionOutcomeRecordV1,
)


def _directional_outcome(
    *,
    action: str,
    movement_percent: float,
    threshold_percent: float,
) -> str:
    if abs(movement_percent) < threshold_percent:
        return "FLAT"

    if action == "CALL":
        return (
            "CORRECT"
            if movement_percent > 0.0
            else "INCORRECT"
        )

    if action == "PUT":
        return (
            "CORRECT"
            if movement_percent < 0.0
            else "INCORRECT"
        )

    raise ValueError("directional action")


def _wait_outcome(
    *,
    movement_percent: float,
    threshold_percent: float,
) -> str:
    absolute = abs(movement_percent)

    if absolute < threshold_percent:
        return "GOOD_WAIT"
    if absolute == threshold_percent:
        return "NEUTRAL_WAIT"
    return "MISSED_OPPORTUNITY"


def evaluate_prediction_outcome(
    value: PredictionOutcomeEvaluationInputV1,
) -> PredictionOutcomeRecordV1:
    """Evaluate one retained prediction from supplied underlying prices."""

    if type(value) is not PredictionOutcomeEvaluationInputV1:
        raise TypeError("value")

    prediction = value.prediction

    movement_points = (
        value.end_underlying_price
        - value.start_underlying_price
    )
    movement_percent = (
        movement_points
        / value.start_underlying_price
        * 100.0
    )
    absolute_movement_percent = abs(
        movement_percent
    )

    if prediction.predicted_action in {
        "CALL",
        "PUT",
    }:
        evaluation_kind = "DIRECTIONAL"
        outcome = _directional_outcome(
            action=prediction.predicted_action,
            movement_percent=movement_percent,
            threshold_percent=value.threshold_percent,
        )
    else:
        evaluation_kind = "ABSTENTION"
        outcome = _wait_outcome(
            movement_percent=movement_percent,
            threshold_percent=value.threshold_percent,
        )

    return PredictionOutcomeRecordV1(
        outcome_id=(
            f"outcome:{prediction.prediction_id}:"
            f"{value.evaluation_due_at.isoformat()}"
        ),
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        decision_result_id=prediction.decision_result_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        evaluation_kind=evaluation_kind,
        prediction_completed_at=prediction.completed_at,
        evaluation_due_at=value.evaluation_due_at,
        evaluated_at=value.evaluated_at,
        evaluation_status="EVALUATED",
        outcome=outcome,
        start_underlying_price=(
            value.start_underlying_price
        ),
        end_underlying_price=(
            value.end_underlying_price
        ),
        movement_points=movement_points,
        movement_percent=movement_percent,
        absolute_movement_percent=(
            absolute_movement_percent
        ),
        evaluation_horizon_seconds=(
            value.evaluation_horizon_seconds
        ),
        threshold_percent=(
            value.threshold_percent
        ),
        evidence_observation_id=(
            value.evaluation_observation_id
        ),
    )


def build_unevaluable_prediction_outcome(
    *,
    prediction,
    evaluation_due_at,
    evaluated_at,
    evaluation_horizon_seconds,
    threshold_percent,
    blocker: str,
) -> PredictionOutcomeRecordV1:
    """Retain an explicit terminal outcome when evaluation evidence is absent."""

    from services.contracts.prediction_record_v1 import (
        PredictionRecordV1,
    )

    if type(prediction) is not PredictionRecordV1:
        raise TypeError("prediction")
    if type(blocker) is not str or not blocker.strip():
        raise ValueError("blocker")

    return PredictionOutcomeRecordV1(
        outcome_id=(
            f"outcome:{prediction.prediction_id}:"
            f"{evaluation_due_at.isoformat()}"
        ),
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        decision_result_id=prediction.decision_result_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        evaluation_kind=(
            "DIRECTIONAL"
            if prediction.predicted_action in {"CALL", "PUT"}
            else "ABSTENTION"
        ),
        prediction_completed_at=prediction.completed_at,
        evaluation_due_at=evaluation_due_at,
        evaluated_at=evaluated_at,
        evaluation_status="UNEVALUABLE",
        outcome="UNEVALUABLE",
        start_underlying_price=None,
        end_underlying_price=None,
        movement_points=None,
        movement_percent=None,
        absolute_movement_percent=None,
        evaluation_horizon_seconds=evaluation_horizon_seconds,
        threshold_percent=threshold_percent,
        evidence_observation_id=None,
        blockers=(blocker.strip(),),
    )
