from datetime import timedelta

import pytest

from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_outcome_evaluator import (
    evaluate_prediction_outcome,
)
from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)
from services.contracts.prediction_outcome_evaluation_input_v1 import (
    PredictionOutcomeEvaluationInputV1,
)
from services.reporting.prediction_performance_report_builder import (
    build_prediction_performance_report,
)
from test_r53_prediction_ledger import records


def _seed(tmp_path):
    prediction_path = tmp_path / "predictions.json"
    outcome_path = tmp_path / "outcomes.json"
    predictions = records()

    PredictionLedger(prediction_path).save_pair(
        predictions
    )

    due = (
        predictions[0].completed_at
        + timedelta(minutes=15)
    )

    nifty = evaluate_prediction_outcome(
        PredictionOutcomeEvaluationInputV1(
            prediction=predictions[0],
            evaluation_observation_id="eval-nifty",
            start_underlying_price=(
                predictions[0].start_underlying_price
            ),
            end_underlying_price=(
                predictions[0].start_underlying_price
                + 100.0
            ),
            evaluation_due_at=due,
            evaluated_at=due,
            evaluation_horizon_seconds=900.0,
            threshold_percent=0.20,
        )
    )

    PredictionOutcomeLedger(outcome_path).save(
        nifty
    )

    return (
        PredictionLedger(prediction_path),
        PredictionOutcomeLedger(outcome_path),
        predictions,
        due,
    )


def test_builds_overall_and_market_metrics_from_ledgers(
    tmp_path,
):
    prediction_ledger, outcome_ledger, _, due = (
        _seed(tmp_path)
    )

    report = build_prediction_performance_report(
        prediction_ledger=prediction_ledger,
        outcome_ledger=outcome_ledger,
        generated_at=due,
        report_id="report-1",
    )

    assert report.overall.prediction_count == 2
    assert report.overall.evaluated_count == 1
    assert report.overall.pending_count == 1
    assert report.overall.directional_accuracy_percent == 100.0
    assert report.nifty.evaluated_count == 1
    assert report.sensex.pending_count == 1
    assert report.execution_mode == "PAPER"
    assert report.read_only is True


def test_report_is_deterministic_for_same_ledgers_and_time(
    tmp_path,
):
    prediction_ledger, outcome_ledger, _, due = (
        _seed(tmp_path)
    )

    first = build_prediction_performance_report(
        prediction_ledger=prediction_ledger,
        outcome_ledger=outcome_ledger,
        generated_at=due,
        report_id="report-1",
    )
    second = build_prediction_performance_report(
        prediction_ledger=prediction_ledger,
        outcome_ledger=outcome_ledger,
        generated_at=due,
        report_id="report-1",
    )

    assert first == second
    assert first.to_json() == second.to_json()


def test_empty_ledgers_build_zero_report(tmp_path):
    generated_at = records()[0].completed_at

    report = build_prediction_performance_report(
        prediction_ledger=PredictionLedger(
            tmp_path / "predictions.json"
        ),
        outcome_ledger=PredictionOutcomeLedger(
            tmp_path / "outcomes.json"
        ),
        generated_at=generated_at,
        report_id="empty-report",
    )

    assert report.source_prediction_count == 0
    assert report.source_outcome_count == 0
    assert report.period_started_at is None
    assert report.overall.directional_accuracy_percent is None


def test_unknown_outcome_prediction_fails_closed(tmp_path):
    prediction_ledger, outcome_ledger, predictions, due = (
        _seed(tmp_path)
    )
    raw = outcome_ledger.all_records()[0]
    document = outcome_ledger._read_document()
    outcome_id = raw["outcome_id"]
    document["records"][outcome_id][
        "prediction_id"
    ] = "unknown-prediction"
    outcome_ledger._write_document(document)

    with pytest.raises(
        ValueError,
        match="unknown prediction",
    ):
        build_prediction_performance_report(
            prediction_ledger=prediction_ledger,
            outcome_ledger=outcome_ledger,
            generated_at=due,
            report_id="report-1",
        )
