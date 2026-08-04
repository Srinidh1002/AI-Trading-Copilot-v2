import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
    ContinuousPaperOrchestrationRuntimeConfigV1,
)
from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)
from services.paper_orchestration.restart_recovery_operation import (
    RestartRecoveryOperation,
    RestartRecoveryTargetV1,
)
from services.paper_portfolio.paper_portfolio_recovery_service import (
    PaperPortfolioRecoveryService,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def clock() -> datetime:
    return NOW


def coordinator():
    return object.__new__(
        DeterministicPaperOrchestrationCycleCoordinator
    )


def cycle_input():
    return object.__new__(PaperOrchestrationCycleInputV1)


def test_portfolio_recovery_converts_decode_failure_to_corrupt():
    persistence = object.__new__(
        PaperPortfolioPersistenceService
    )
    service = PaperPortfolioRecoveryService(persistence)

    with patch.object(
        persistence,
        "get",
        side_effect=ValueError("typed P8 snapshot integrity mismatch"),
    ):
        result = service.recover("portfolio-1", NOW)

    assert result.status == "CORRUPT"
    assert result.reconciliation_codes == (
        "PERSISTENCE_DECODE_FAILED",
    )
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_missing_portfolio_recovery_is_blocked():
    persistence = object.__new__(
        PaperPortfolioPersistenceService
    )
    service = PaperPortfolioRecoveryService(persistence)

    with patch.object(
        persistence,
        "get",
        return_value=None,
    ):
        result = service.recover("portfolio-1", NOW)

    assert result.status == "BLOCKED"
    assert result.blockers == ("PORTFOLIO_NOT_FOUND",)


def test_restart_recovery_captures_target_exception_without_escape():
    operation = RestartRecoveryOperation(
        targets=(
            RestartRecoveryTargetV1(
                target_type="P7_TRADE",
                target_id="trade-1",
                recovery_authority=lambda target_id, recovered_at: (
                    (_ for _ in ()).throw(
                        RuntimeError("corrupt P7 state")
                    )
                ),
            ),
            RestartRecoveryTargetV1(
                target_type="P8_PORTFOLIO",
                target_id="portfolio-1",
                recovery_authority=lambda target_id, recovered_at: (
                    SimpleNamespace(status="RECOVERED")
                ),
            ),
        ),
        clock=clock,
    )

    result = operation()

    assert result["success"] is False
    assert result["results"][0]["status"] == "ERROR"
    assert result["results"][0]["error"] == "corrupt P7 state"
    assert result["results"][1]["status"] == "RECOVERED"


def test_runtime_startup_failure_prevents_both_cycle_lanes():
    calls = []
    opportunity = coordinator()
    monitoring = coordinator()

    adapter = ContinuousPaperOrchestrationRuntimeAdapter(
        opportunity_coordinator=opportunity,
        opportunity_input_factory=lambda: (
            calls.append("OPPORTUNITY") or cycle_input()
        ),
        monitoring_coordinator=monitoring,
        monitoring_input_factory=lambda: (
            calls.append("MONITORING") or cycle_input()
        ),
        config=ContinuousPaperOrchestrationRuntimeConfigV1(
            interval_seconds=0,
        ),
        startup_operation=lambda: {
            "success": False,
            "error": "startup recovery failed",
        },
    )

    stats = adapter.run(max_cycles=2)

    assert calls == []
    assert stats["startup_status"] == "FAILED"


def test_journal_rejects_record_key_mismatch_before_execution(
    tmp_path,
):
    path = tmp_path / "journal.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": {
                    "cycle-key-1": {
                        "cycle_idempotency_key": (
                            "different-cycle-key"
                        )
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    journal = PaperOrchestrationJournal(path)

    with pytest.raises(
        ValueError,
        match="journal record key mismatch",
    ):
        journal.classify(
            cycle_idempotency_key="cycle-key-1",
            cycle_input_semantic_hash="a" * 64,
        )


def test_partial_temporary_journal_file_does_not_replace_valid_state(
    tmp_path,
):
    path = tmp_path / "journal.json"
    valid = {
        "version": 1,
        "records": {},
    }
    path.write_text(
        json.dumps(valid),
        encoding="utf-8",
    )
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        "{broken-temporary-json",
        encoding="utf-8",
    )

    journal = PaperOrchestrationJournal(path)

    assert journal.classify(
        cycle_idempotency_key="cycle-key-1",
        cycle_input_semantic_hash="a" * 64,
    ) == "NEW"
    assert json.loads(
        path.read_text(encoding="utf-8")
    ) == valid
