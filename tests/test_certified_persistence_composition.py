from datetime import datetime, timezone

import pytest

from services.paper_orchestration.certified_persistence_composition import (
    CertifiedCoordinatorPairV1,
    build_certified_coordinators,
    build_certified_persistence_paths,
    build_certified_restart_recovery,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.restart_recovery_operation import (
    RestartRecoveryOperation,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def clock():
    return NOW


def test_builds_separate_opportunity_and_monitoring_journals(tmp_path):
    paths = build_certified_persistence_paths(tmp_path / "runtime")
    result = build_certified_coordinators(
        opportunity_cycle_executor=lambda value: value,
        monitoring_cycle_executor=lambda value: value,
        clock=clock,
        paths=paths,
    )

    assert type(result) is CertifiedCoordinatorPairV1
    assert type(result.opportunity_journal) is PaperOrchestrationJournal
    assert type(result.monitoring_journal) is PaperOrchestrationJournal
    assert (
        result.opportunity_journal.file_path
        != result.monitoring_journal.file_path
    )
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_paths_must_remain_under_root(tmp_path):
    root = tmp_path / "root"
    with pytest.raises(ValueError, match="root_directory"):
        type(build_certified_persistence_paths(root))(
            root_directory=root,
            opportunity_journal_path=tmp_path / "outside.json",
            monitoring_journal_path=root / "monitoring.json",
        )


def test_restart_recovery_wires_exact_p7_and_p8_targets():
    operation = build_certified_restart_recovery(
        p7_trade_ids=("trade-1", "trade-2"),
        p8_portfolio_ids=("portfolio-1",),
        p7_recovery_authority=lambda target_id, now: type(
            "Recovery",
            (),
            {"status": "RECOVERED"},
        )(),
        p8_recovery_authority=lambda target_id, now: type(
            "Recovery",
            (),
            {"status": "RECOVERED"},
        )(),
        clock=clock,
    )

    assert type(operation) is RestartRecoveryOperation
    assert tuple(
        (item.target_type, item.target_id)
        for item in operation.targets
    ) == (
        ("P7_TRADE", "trade-1"),
        ("P7_TRADE", "trade-2"),
        ("P8_PORTFOLIO", "portfolio-1"),
    )
    assert operation()["success"] is True


def test_duplicate_recovery_target_is_rejected():
    with pytest.raises(ValueError, match="duplicate recovery target"):
        build_certified_restart_recovery(
            p7_trade_ids=("trade-1", "trade-1"),
            p8_portfolio_ids=(),
            p7_recovery_authority=lambda *_: object(),
            p8_recovery_authority=lambda *_: object(),
            clock=clock,
        )
