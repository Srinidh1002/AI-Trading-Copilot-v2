from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
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


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)

INPUT_HASH = "a" * 64


def cycle_input(
    *,
    cycle_id: str,
    cycle_key: str,
) -> PaperOrchestrationCycleInputV1:
    value = object.__new__(
        PaperOrchestrationCycleInputV1
    )

    fields = {
        "cycle_id": cycle_id,
        "cycle_idempotency_key": cycle_key,
        "cycle_requested_at": NOW,
        "market_timestamp": NOW,
        "received_at": NOW,
        "underlying_symbol": "NIFTY",
        "metadata": {
            "execution_mode": "PAPER",
            "broker_order_submission": False,
        },
    }

    for name, item in fields.items():
        object.__setattr__(
            value,
            name,
            item,
        )

    return value


def completed_no_action_result(
    cycle: PaperOrchestrationCycleInputV1,
    *,
    source: str,
) -> PaperOrchestrationCycleResultV1:
    stage = PaperOrchestrationStageResultV1(
        stage_result_id=(
            f"{cycle.cycle_id}:"
            f"{source.lower()}:stage"
        ),
        cycle_id=cycle.cycle_id,
        stage="P7_LIFECYCLE",
        status="NO_ACTION",
        started_at=NOW,
        completed_at=NOW,
        source_result_type=source,
        paper_action_occurred=False,
        metadata={
            "execution_mode": "PAPER",
            "broker_order_submission": False,
        },
    )

    return PaperOrchestrationCycleResultV1(
        cycle_result_id=(
            f"{cycle.cycle_id}:"
            f"{source.lower()}:result"
        ),
        cycle_id=cycle.cycle_id,
        cycle_idempotency_key=(
            cycle.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=INPUT_HASH,
        cycle_status="COMPLETED_NO_ACTION",
        terminal_stage="P7_LIFECYCLE",
        started_at=NOW,
        completed_at=NOW,
        stage_results=(stage,),
        metadata={
            "source": source,
            "execution_mode": "PAPER",
            "broker_order_submission": False,
        },
    )


def coordinator(
    *,
    journal_path,
    calls,
    source,
):
    def execute(cycle):
        calls.append(
            (
                source,
                cycle.cycle_id,
                cycle.cycle_idempotency_key,
            )
        )

        return completed_no_action_result(
            cycle,
            source=source,
        )

    return DeterministicPaperOrchestrationCycleCoordinator(
        journal=PaperOrchestrationJournal(
            journal_path
        ),
        cycle_executor=execute,
        clock=lambda: NOW,
    )


def test_exact_monitoring_replay_is_duplicate_no_change(
    tmp_path,
):
    calls = []

    monitoring = coordinator(
        journal_path=(
            tmp_path / "monitoring-journal.json"
        ),
        calls=calls,
        source="MONITORING",
    )

    value = cycle_input(
        cycle_id="monitor-cycle-1",
        cycle_key="monitor-key-1",
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=INPUT_HASH,
    ):
        first = monitoring.run(value)
        second = monitoring.run(value)

    assert first.cycle_status == "COMPLETED_NO_ACTION"
    assert second.cycle_status == "DUPLICATE_NO_CHANGE"
    assert second.duplicate_of_cycle_result_id == (
        first.cycle_result_id
    )

    assert calls == [
        (
            "MONITORING",
            "monitor-cycle-1",
            "monitor-key-1",
        )
    ]

    assert monitoring.journal.count() == 1
    assert second.paper_actions == ()
    assert second.execution_mode == "PAPER"
    assert second.live_execution_eligible is False


def test_fresh_coordinator_instance_retains_duplicate_protection(
    tmp_path,
):
    journal_path = (
        tmp_path / "monitoring-journal.json"
    )

    first_calls = []
    first_coordinator = coordinator(
        journal_path=journal_path,
        calls=first_calls,
        source="MONITORING",
    )

    value = cycle_input(
        cycle_id="monitor-cycle-1",
        cycle_key="monitor-key-1",
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=INPUT_HASH,
    ):
        first = first_coordinator.run(value)

    second_calls = []
    restarted_coordinator = coordinator(
        journal_path=journal_path,
        calls=second_calls,
        source="MONITORING",
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=INPUT_HASH,
    ):
        replay = restarted_coordinator.run(value)

    assert first.cycle_status == "COMPLETED_NO_ACTION"
    assert replay.cycle_status == "DUPLICATE_NO_CHANGE"
    assert replay.duplicate_of_cycle_result_id == (
        first.cycle_result_id
    )

    assert first_calls == [
        (
            "MONITORING",
            "monitor-cycle-1",
            "monitor-key-1",
        )
    ]

    assert second_calls == []
    assert restarted_coordinator.journal.count() == 1


def test_scheduled_adapter_path_retains_restart_duplicate_guard(
    tmp_path,
):
    opportunity_path = (
        tmp_path / "opportunity-journal.json"
    )
    monitoring_path = (
        tmp_path / "monitoring-journal.json"
    )

    opportunity_cycle = cycle_input(
        cycle_id="opportunity-cycle-1",
        cycle_key="opportunity-key-1",
    )

    monitoring_cycle = cycle_input(
        cycle_id="monitor-cycle-1",
        cycle_key="monitor-key-1",
    )

    first_opportunity_calls = []
    first_monitoring_calls = []

    first_adapter = (
        ContinuousPaperOrchestrationRuntimeAdapter(
            opportunity_coordinator=coordinator(
                journal_path=opportunity_path,
                calls=first_opportunity_calls,
                source="OPPORTUNITY",
            ),
            opportunity_input_factory=(
                lambda: opportunity_cycle
            ),
            monitoring_coordinator=coordinator(
                journal_path=monitoring_path,
                calls=first_monitoring_calls,
                source="MONITORING",
            ),
            monitoring_input_factory=(
                lambda: monitoring_cycle
            ),
            config=(
                ContinuousPaperOrchestrationRuntimeConfigV1(
                    interval_seconds=0,
                )
            ),
            startup_operation=lambda: {
                "success": True,
                "status": "RECOVERED",
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
            monotonic_function=lambda: 1.0,
            sleep_function=lambda _: None,
        )
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=INPUT_HASH,
    ):
        first_report = first_adapter.run_cycle()

    assert first_report["status"] == "COMPLETED"
    assert first_opportunity_calls == [
        (
            "OPPORTUNITY",
            "opportunity-cycle-1",
            "opportunity-key-1",
        )
    ]
    assert first_monitoring_calls == [
        (
            "MONITORING",
            "monitor-cycle-1",
            "monitor-key-1",
        )
    ]

    restarted_opportunity_calls = []
    restarted_monitoring_calls = []

    restarted_adapter = (
        ContinuousPaperOrchestrationRuntimeAdapter(
            opportunity_coordinator=coordinator(
                journal_path=opportunity_path,
                calls=restarted_opportunity_calls,
                source="OPPORTUNITY",
            ),
            opportunity_input_factory=(
                lambda: opportunity_cycle
            ),
            monitoring_coordinator=coordinator(
                journal_path=monitoring_path,
                calls=restarted_monitoring_calls,
                source="MONITORING",
            ),
            monitoring_input_factory=(
                lambda: monitoring_cycle
            ),
            config=(
                ContinuousPaperOrchestrationRuntimeConfigV1(
                    interval_seconds=0,
                )
            ),
            startup_operation=lambda: {
                "success": True,
                "status": "RECOVERED",
                "execution_mode": "PAPER",
                "live_execution_eligible": False,
                "broker_order_submission": False,
            },
            monotonic_function=lambda: 2.0,
            sleep_function=lambda _: None,
        )
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=INPUT_HASH,
    ):
        restarted_report = (
            restarted_adapter.run_cycle()
        )

    assert restarted_report["status"] == "COMPLETED"

    # Both scheduled operations were classified from their
    # persisted journals before their executors could run.
    assert restarted_opportunity_calls == []
    assert restarted_monitoring_calls == []

    assert (
        restarted_adapter
        .opportunity_coordinator
        .journal
        .count()
        == 1
    )
    assert (
        restarted_adapter
        .monitoring_coordinator
        .journal
        .count()
        == 1
    )


def test_same_key_with_changed_payload_fails_closed(
    tmp_path,
):
    calls = []

    monitoring = coordinator(
        journal_path=(
            tmp_path / "monitoring-journal.json"
        ),
        calls=calls,
        source="MONITORING",
    )

    first_cycle = cycle_input(
        cycle_id="monitor-cycle-1",
        cycle_key="shared-monitor-key",
    )

    changed_cycle = cycle_input(
        cycle_id="monitor-cycle-2",
        cycle_key="shared-monitor-key",
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value="a" * 64,
    ):
        first = monitoring.run(first_cycle)

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value="b" * 64,
    ):
        conflict = monitoring.run(changed_cycle)

    assert first.cycle_status == "COMPLETED_NO_ACTION"
    assert conflict.cycle_status == "FAILED"
    assert conflict.terminal_stage == "PERSISTENCE"
    assert conflict.errors == (
        "IDEMPOTENCY_PAYLOAD_CONFLICT",
    )

    assert calls == [
        (
            "MONITORING",
            "monitor-cycle-1",
            "shared-monitor-key",
        )
    ]