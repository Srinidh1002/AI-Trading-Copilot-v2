from datetime import timedelta
from pathlib import Path

from services.contracts.prediction_outcome_evaluation_input_v1 import (
    PredictionOutcomeEvaluationInputV1,
)
from services.paper_orchestration.certified_prediction_performance_reporting import (
    CertifiedPredictionReportingCompositionV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_outcome_evaluator import (
    evaluate_prediction_outcome,
)
from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)
from services.reporting.prediction_performance_report_archive import (
    PredictionPerformanceReportArchive,
)
from test_r53_prediction_ledger import records


def _composition(tmp_path):
    prediction_ledger = PredictionLedger(
        tmp_path / "prediction_ledger.json"
    )
    outcome_ledger = PredictionOutcomeLedger(
        tmp_path / "prediction_outcome_ledger.json"
    )
    archive = PredictionPerformanceReportArchive(
        tmp_path / "prediction_reports"
    )
    return CertifiedPredictionReportingCompositionV1(
        prediction_ledger=prediction_ledger,
        outcome_ledger=outcome_ledger,
        archive=archive,
    )


def _seed(composition):
    predictions = records()
    composition.prediction_ledger.save_pair(
        predictions
    )
    due = (
        predictions[0].completed_at
        + timedelta(minutes=15)
    )

    outcome = evaluate_prediction_outcome(
        PredictionOutcomeEvaluationInputV1(
            prediction=predictions[0],
            evaluation_observation_id="report-eval-nifty",
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
    composition.outcome_ledger.save(outcome)
    return predictions, due


def test_end_to_end_build_and_save_is_ledger_grounded(
    tmp_path,
):
    composition = _composition(tmp_path)
    _, due = _seed(composition)

    report, persisted = composition.build_and_save(
        generated_at=due,
        report_id="certified-report-1",
    )

    assert report.source_prediction_count == 2
    assert report.source_outcome_count == 1
    assert report.overall.pending_count == 1
    assert report.nifty.directional_accuracy_percent == 100.0
    assert report.sensex.pending_count == 1
    assert Path(persisted["json_path"]).is_file()
    assert Path(persisted["text_path"]).is_file()
    assert composition.archive.load_json(
        report.report_id
    ) == report.to_dict()


def test_restart_rebuild_is_deterministic_and_overwrites_same_report(
    tmp_path,
):
    first = _composition(tmp_path)
    _, due = _seed(first)

    first_report, first_result = first.build_and_save(
        generated_at=due,
        report_id="restart-report",
    )

    restarted = _composition(tmp_path)
    second_report, second_result = restarted.build_and_save(
        generated_at=due,
        report_id="restart-report",
    )

    assert first_report == second_report
    assert first_report.to_json() == second_report.to_json()
    assert first_result["json_path"] == second_result["json_path"]
    assert first_result["text_path"] == second_result["text_path"]
    assert len(
        list(
            (tmp_path / "prediction_reports").glob(
                "restart-report.*"
            )
        )
    ) == 2


def test_composition_is_paper_only_read_only(
    tmp_path,
):
    composition = _composition(tmp_path)

    assert composition.execution_mode == "PAPER"
    assert composition.live_execution_eligible is False
    assert composition.broker_order_submission is False
    assert composition.read_only is True
