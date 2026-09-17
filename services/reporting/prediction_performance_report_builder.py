"""Deterministic read-only prediction performance reporting."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from services.contracts.prediction_performance_report_v1 import (
    PredictionPerformanceMetricsV1,
    PredictionPerformanceReportV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _metrics(
    predictions: tuple[dict, ...],
    outcomes: tuple[dict, ...],
) -> PredictionPerformanceMetricsV1:
    action_counts = Counter(
        item["predicted_action"]
        for item in predictions
    )
    outcome_counts = Counter(
        item["outcome"]
        for item in outcomes
    )

    prediction_ids = {
        item["prediction_id"]
        for item in predictions
    }
    outcome_prediction_ids = {
        item["prediction_id"]
        for item in outcomes
    }

    if not outcome_prediction_ids.issubset(
        prediction_ids
    ):
        raise ValueError(
            "outcome references unknown prediction"
        )

    if len(outcome_prediction_ids) != len(outcomes):
        raise ValueError(
            "multiple outcomes for one prediction are unsupported"
        )

    correct = outcome_counts["CORRECT"]
    incorrect = outcome_counts["INCORRECT"]
    flat = outcome_counts["FLAT"]
    good_wait = outcome_counts["GOOD_WAIT"]
    missed = outcome_counts["MISSED_OPPORTUNITY"]
    neutral = outcome_counts["NEUTRAL_WAIT"]
    unevaluable = outcome_counts["UNEVALUABLE"]

    directional_resolved = correct + incorrect
    abstention_resolved = (
        good_wait
        + missed
        + neutral
    )
    wait_denominator = good_wait + missed

    return PredictionPerformanceMetricsV1(
        prediction_count=len(predictions),
        evaluated_count=len(outcomes),
        pending_count=(
            len(predictions)
            - len(outcomes)
        ),
        unevaluable_count=unevaluable,
        directional_resolved_count=(
            directional_resolved
        ),
        directional_correct_count=correct,
        directional_incorrect_count=incorrect,
        directional_flat_count=flat,
        abstention_resolved_count=(
            abstention_resolved
        ),
        good_wait_count=good_wait,
        missed_opportunity_count=missed,
        neutral_wait_count=neutral,
        directional_accuracy_percent=(
            correct
            / directional_resolved
            * 100.0
            if directional_resolved
            else None
        ),
        wait_quality_percent=(
            good_wait
            / wait_denominator
            * 100.0
            if wait_denominator
            else None
        ),
        action_distribution=tuple(
            sorted(action_counts.items())
        ),
        outcome_distribution=tuple(
            sorted(outcome_counts.items())
        ),
    )


def build_prediction_performance_report(
    *,
    prediction_ledger: PredictionLedger,
    outcome_ledger: PredictionOutcomeLedger,
    generated_at: datetime,
    report_id: str,
) -> PredictionPerformanceReportV1:
    """Build one exact report from immutable ledger contents."""

    if type(prediction_ledger) is not PredictionLedger:
        raise TypeError("prediction_ledger")
    if type(outcome_ledger) is not PredictionOutcomeLedger:
        raise TypeError("outcome_ledger")

    generated = _aware(
        generated_at,
        "generated_at",
    )

    predictions = prediction_ledger.all_records()
    outcomes = outcome_ledger.all_records()

    prediction_by_id = {
        item["prediction_id"]: item
        for item in predictions
    }

    for outcome in outcomes:
        prediction = prediction_by_id.get(
            outcome["prediction_id"]
        )
        if prediction is None:
            raise ValueError(
                "outcome references unknown prediction"
            )
        if (
            outcome["underlying_symbol"]
            != prediction["underlying_symbol"]
            or outcome["exchange"]
            != prediction["exchange"]
        ):
            raise ValueError(
                "prediction/outcome market identity mismatch"
            )

    started = (
        datetime.fromisoformat(
            predictions[0]["completed_at"]
        )
        if predictions
        else None
    )
    ended = (
        datetime.fromisoformat(
            predictions[-1]["completed_at"]
        )
        if predictions
        else None
    )

    nifty_predictions = tuple(
        item
        for item in predictions
        if item["underlying_symbol"] == "NIFTY"
    )
    sensex_predictions = tuple(
        item
        for item in predictions
        if item["underlying_symbol"] == "SENSEX"
    )
    nifty_outcomes = tuple(
        item
        for item in outcomes
        if item["underlying_symbol"] == "NIFTY"
    )
    sensex_outcomes = tuple(
        item
        for item in outcomes
        if item["underlying_symbol"] == "SENSEX"
    )

    return PredictionPerformanceReportV1(
        report_id=report_id,
        generated_at=generated,
        period_started_at=started,
        period_ended_at=ended,
        overall=_metrics(
            predictions,
            outcomes,
        ),
        nifty=_metrics(
            nifty_predictions,
            nifty_outcomes,
        ),
        sensex=_metrics(
            sensex_predictions,
            sensex_outcomes,
        ),
        source_prediction_count=(
            len(predictions)
        ),
        source_outcome_count=len(outcomes),
    )
