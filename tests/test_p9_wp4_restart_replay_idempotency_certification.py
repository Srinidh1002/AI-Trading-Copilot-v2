import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
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


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def clock() -> datetime:
    return NOW


def cycle_input() -> PaperOrchestrationCycleInputV1:
    value = object.__new__(PaperOrchestrationCycleInputV1)
    object.__setattr__(value, "cycle_id", "cycle-1")
    object.__setattr__(
        value,
        "cycle_idempotency_key",
        "cycle-key-1",
    )
    return value


def cycle_result(
    value: PaperOrchestrationCycleInputV1,
    semantic_hash: str,
) -> PaperOrchestrationCycleResultV1:
    result = object.__new__(PaperOrchestrationCycleResultV1)

    fields = {
        "cycle_result_id": f"{value.cycle_id}:result",
        "cycle_id": value.cycle_id,
        "cycle_idempotency_key": value.cycle_idempotency_key,
        "cycle_input_semantic_hash": semantic_hash,
        "cycle_status": "COMPLETED_NO_ACTION",
        "terminal_stage": "PERSISTENCE",
        "started_at": NOW,
        "completed_at": NOW,
        "stage_results": (),
        "paper_actions": (),
        "blockers": (),
        "warnings": (),
        "errors": (),
        "duplicate_of_cycle_result_id": None,
        "metadata": {},
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "schema_version": "paper_orchestration_cycle_result.v1",
    }
    for name, field_value in fields.items():
        object.__setattr__(result, name, field_value)

    return result


def coordinator(
    journal: PaperOrchestrationJournal,
    calls: list[str],
) -> DeterministicPaperOrchestrationCycleCoordinator:
    def execute(value):
        calls.append(value.cycle_id)
        return cycle_result(value, HASH_A)

    return DeterministicPaperOrchestrationCycleCoordinator(
        journal=journal,
        cycle_executor=execute,
        clock=clock,
    )


def test_restart_same_payload_returns_duplicate_without_reexecution(
    tmp_path,
):
    journal_path = tmp_path / "p9-journal.json"
    first_calls = []
    value = cycle_input()

    first = coordinator(
        PaperOrchestrationJournal(journal_path),
        first_calls,
    )
    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH_A,
    ):
        original = first.run(value)

    restart_calls = []
    restarted = coordinator(
        PaperOrchestrationJournal(journal_path),
        restart_calls,
    )
    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH_A,
    ):
        duplicate = restarted.run(value)

    assert original.cycle_status == "COMPLETED_NO_ACTION"
    assert first_calls == ["cycle-1"]
    assert restart_calls == []
    assert duplicate.cycle_status == "DUPLICATE_NO_CHANGE"
    assert (
        duplicate.duplicate_of_cycle_result_id
        == original.cycle_result_id
    )


def test_restart_same_key_different_payload_fails_closed(
    tmp_path,
):
    journal_path = tmp_path / "p9-journal.json"
    value = cycle_input()
    first_calls = []

    first = coordinator(
        PaperOrchestrationJournal(journal_path),
        first_calls,
    )
    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH_A,
    ):
        first.run(value)

    conflict_calls = []
    restarted = coordinator(
        PaperOrchestrationJournal(journal_path),
        conflict_calls,
    )
    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH_B,
    ):
        conflict = restarted.run(value)

    assert conflict_calls == []
    assert conflict.cycle_status == "FAILED"
    assert conflict.terminal_stage == "PERSISTENCE"
    assert conflict.errors == (
        "IDEMPOTENCY_PAYLOAD_CONFLICT",
    )


def test_journal_survives_fresh_instance_replay(
    tmp_path,
):
    journal_path = tmp_path / "p9-journal.json"
    value = cycle_input()
    calls = []

    initial = coordinator(
        PaperOrchestrationJournal(journal_path),
        calls,
    )
    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH_A,
    ):
        initial.run(value)

    recovered_journal = PaperOrchestrationJournal(
        journal_path
    )
    raw = recovered_journal.get_raw("cycle-key-1")

    assert raw is not None
    assert raw["cycle_idempotency_key"] == "cycle-key-1"
    assert raw["cycle_input_semantic_hash"] == HASH_A
    assert (
        raw["cycle_result"]["cycle_result_id"]
        == "cycle-1:result"
    )


def test_corrupt_journal_fails_before_cycle_execution(
    tmp_path,
):
    journal_path = tmp_path / "p9-journal.json"
    journal_path.write_text("{not-json", encoding="utf-8")
    calls = []
    value = cycle_input()
    restarted = coordinator(
        PaperOrchestrationJournal(journal_path),
        calls,
    )

    with (
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH_A,
        ),
        pytest.raises(
            ValueError,
            match="invalid JSON in orchestration journal",
        ),
    ):
        restarted.run(value)

    assert calls == []


def test_restart_recovery_requires_every_target_to_recover():
    operation = RestartRecoveryOperation(
        targets=(
            RestartRecoveryTargetV1(
                target_type="P7_TRADE",
                target_id="trade-1",
                recovery_authority=lambda target_id, recovered_at: (
                    SimpleNamespace(status="RECOVERED")
                ),
            ),
            RestartRecoveryTargetV1(
                target_type="P8_PORTFOLIO",
                target_id="portfolio-1",
                recovery_authority=lambda target_id, recovered_at: (
                    SimpleNamespace(status="CORRUPT")
                ),
            ),
        ),
        clock=clock,
    )

    result = operation()

    assert result["success"] is False
    assert [item["status"] for item in result["results"]] == [
        "RECOVERED",
        "CORRUPT",
    ]
    assert result["execution_mode"] == "PAPER"
    assert result["live_execution_eligible"] is False
