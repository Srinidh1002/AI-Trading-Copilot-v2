from services.paper_orchestration.certified_persistence_composition import (
    build_certified_persistence_paths,
    build_certified_prediction_outcome_ledger,
)
from services.paper_orchestration.prediction_outcome_ledger import (
    PredictionOutcomeLedger,
)


def test_certified_outcome_ledger_uses_separate_path(
    tmp_path,
):
    paths = build_certified_persistence_paths(
        tmp_path / "runtime"
    )

    ledger = build_certified_prediction_outcome_ledger(
        paths=paths
    )

    assert type(ledger) is PredictionOutcomeLedger
    assert (
        ledger.file_path
        == paths.prediction_outcome_ledger_path
    )
    assert ledger.file_path not in {
        paths.opportunity_journal_path,
        paths.monitoring_journal_path,
        paths.parent_decision_journal_path,
        paths.prediction_ledger_path,
    }
