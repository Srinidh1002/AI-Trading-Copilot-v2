from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

import pytest

from services.contracts.prediction_performance_report_v1 import (
    PredictionPerformanceMetricsV1,
    PredictionPerformanceReportV1,
)


NOW = datetime(
    2026,
    8,
    5,
    12,
    0,
    tzinfo=timezone.utc,
)


def metrics(
    *,
    predictions=4,
    evaluated=3,
    pending=1,
    correct=1,
    incorrect=1,
    flat=0,
    good_wait=1,
    missed=0,
    neutral=0,
    unevaluable=0,
    actions=(
        ("CALL", 2),
        ("WAIT", 2),
    ),
    outcomes=(
        ("CORRECT", 1),
        ("GOOD_WAIT", 1),
        ("INCORRECT", 1),
    ),
):
    directional_resolved = correct + incorrect
    abstention_resolved = good_wait + missed + neutral
    wait_denominator = good_wait + missed

    return PredictionPerformanceMetricsV1(
        prediction_count=predictions,
        evaluated_count=evaluated,
        pending_count=pending,
        unevaluable_count=unevaluable,
        directional_resolved_count=directional_resolved,
        directional_correct_count=correct,
        directional_incorrect_count=incorrect,
        directional_flat_count=flat,
        abstention_resolved_count=abstention_resolved,
        good_wait_count=good_wait,
        missed_opportunity_count=missed,
        neutral_wait_count=neutral,
        directional_accuracy_percent=(
            correct / directional_resolved * 100.0
            if directional_resolved
            else None
        ),
        wait_quality_percent=(
            good_wait / wait_denominator * 100.0
            if wait_denominator
            else None
        ),
        action_distribution=actions,
        outcome_distribution=outcomes,
    )


def report():
    nifty = metrics(
        predictions=2,
        evaluated=2,
        pending=0,
        correct=1,
        incorrect=1,
        good_wait=0,
        actions=(("CALL", 2),),
        outcomes=(
            ("CORRECT", 1),
            ("INCORRECT", 1),
        ),
    )
    sensex = metrics(
        predictions=2,
        evaluated=1,
        pending=1,
        correct=0,
        incorrect=0,
        good_wait=1,
        actions=(("WAIT", 2),),
        outcomes=(("GOOD_WAIT", 1),),
    )

    return PredictionPerformanceReportV1(
        report_id="prediction-report-1",
        generated_at=NOW,
        period_started_at=NOW,
        period_ended_at=NOW,
        overall=metrics(),
        nifty=nifty,
        sensex=sensex,
        source_prediction_count=4,
        source_outcome_count=3,
    )


def test_report_is_immutable_deterministic_and_read_only():
    value = report()

    assert value.to_json() == report().to_json()

    with pytest.raises(FrozenInstanceError):
        value.report_id = "changed"

    with pytest.raises(ValueError):
        replace(value, execution_mode="LIVE")

    with pytest.raises(ValueError):
        replace(value, broker_order_submission=True)

    with pytest.raises(ValueError):
        replace(value, read_only=False)


def test_directional_accuracy_is_resolved_only():
    value = metrics()

    assert value.directional_accuracy_percent == 50.0

    with pytest.raises(
        ValueError,
        match="directional accuracy",
    ):
        replace(
            value,
            directional_accuracy_percent=75.0,
        )


def test_wait_quality_excludes_neutral_wait():
    value = metrics(
        predictions=3,
        evaluated=3,
        pending=0,
        correct=0,
        incorrect=0,
        good_wait=1,
        missed=1,
        neutral=1,
        actions=(("WAIT", 3),),
        outcomes=(
            ("GOOD_WAIT", 1),
            ("MISSED_OPPORTUNITY", 1),
            ("NEUTRAL_WAIT", 1),
        ),
    )

    assert value.wait_quality_percent == 50.0


def test_empty_metrics_require_none_percentages():
    value = metrics(
        predictions=0,
        evaluated=0,
        pending=0,
        correct=0,
        incorrect=0,
        good_wait=0,
        actions=(),
        outcomes=(),
    )

    assert value.directional_accuracy_percent is None
    assert value.wait_quality_percent is None


def test_distribution_and_report_counts_must_reconcile():
    with pytest.raises(
        ValueError,
        match="action distribution",
    ):
        metrics(
            actions=(("CALL", 1),),
        )

    with pytest.raises(
        ValueError,
        match="source prediction",
    ):
        replace(
            report(),
            source_prediction_count=5,
        )
