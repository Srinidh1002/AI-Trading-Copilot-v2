from services.paper_orchestration.certified_persistence_composition import (
    build_certified_persistence_paths,
    build_certified_prediction_performance_report_archive,
)
from services.reporting.prediction_performance_report_archive import (
    PredictionPerformanceReportArchive,
)


def test_certified_report_archive_uses_separate_default_path(
    tmp_path,
):
    paths = build_certified_persistence_paths(
        tmp_path
    )

    archive = (
        build_certified_prediction_performance_report_archive(
            paths=paths
        )
    )

    assert type(archive) is PredictionPerformanceReportArchive
    assert archive.base_directory == (
        tmp_path / "prediction_reports"
    ).resolve()
    assert archive.base_directory not in {
        paths.opportunity_journal_path,
        paths.monitoring_journal_path,
        paths.parent_decision_journal_path,
        paths.prediction_ledger_path,
        paths.prediction_outcome_ledger_path,
    }


def test_report_archive_builder_creates_nothing_eagerly(
    tmp_path,
):
    paths = build_certified_persistence_paths(
        tmp_path
    )

    build_certified_prediction_performance_report_archive(
        paths=paths
    )

    assert not paths.prediction_report_directory.exists()
