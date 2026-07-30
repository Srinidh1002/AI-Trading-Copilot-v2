from datetime import datetime, timezone
from unittest.mock import patch

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
    ContinuousPaperOrchestrationRuntimeConfigV1,
)
from services.paper_orchestration.deterministic_cycle_coordinator import (
    DeterministicPaperOrchestrationCycleCoordinator,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def cycle_input():
    return object.__new__(PaperOrchestrationCycleInputV1)


def cycle_result() -> PaperOrchestrationCycleResultV1:
    value = object.__new__(
        PaperOrchestrationCycleResultV1
    )

    object.__setattr__(
        value,
        "cycle_result_id",
        "cycle-result-1",
    )
    object.__setattr__(
        value,
        "cycle_id",
        "cycle-1",
    )
    object.__setattr__(
        value,
        "cycle_idempotency_key",
        "cycle-key-1",
    )
    object.__setattr__(
        value,
        "cycle_input_semantic_hash",
        "a" * 64,
    )
    object.__setattr__(
        value,
        "cycle_status",
        "COMPLETED_NO_ACTION",
    )
    object.__setattr__(
        value,
        "terminal_stage",
        "PERSISTENCE",
    )
    object.__setattr__(
        value,
        "started_at",
        NOW,
    )
    object.__setattr__(
        value,
        "completed_at",
        NOW,
    )
    object.__setattr__(
        value,
        "stage_results",
        (),
    )
    object.__setattr__(
        value,
        "paper_actions",
        (),
    )
    object.__setattr__(
        value,
        "blockers",
        (),
    )
    object.__setattr__(
        value,
        "warnings",
        (),
    )
    object.__setattr__(
        value,
        "errors",
        (),
    )
    object.__setattr__(
        value,
        "duplicate_of_cycle_result_id",
        None,
    )
    object.__setattr__(
        value,
        "metadata",
        {},
    )
    object.__setattr__(
        value,
        "execution_mode",
        "PAPER",
    )
    object.__setattr__(
        value,
        "live_execution_eligible",
        False,
    )
    object.__setattr__(
        value,
        "schema_version",
        "paper_orchestration_cycle_result.v1",
    )

    return value


def coordinator():
    return object.__new__(
        DeterministicPaperOrchestrationCycleCoordinator
    )


def test_runtime_adapter_invokes_opportunity_then_monitoring():
    order = []
    opportunity = coordinator()
    monitoring = coordinator()

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=lambda value: (
                order.append("OPPORTUNITY") or cycle_result()
            ),
        ),
        patch.object(
            monitoring,
            "run",
            side_effect=lambda value: (
                order.append("MONITORING") or cycle_result()
            ),
        ),
    ):
        adapter = ContinuousPaperOrchestrationRuntimeAdapter(
            opportunity_coordinator=opportunity,
            opportunity_input_factory=cycle_input,
            monitoring_coordinator=monitoring,
            monitoring_input_factory=cycle_input,
            config=ContinuousPaperOrchestrationRuntimeConfigV1(
                interval_seconds=0,
            ),
            monotonic_function=lambda: 1.0,
            sleep_function=lambda value: None,
        )
        report = adapter.run_cycle()

    assert report["status"] == "COMPLETED"
    assert order == ["OPPORTUNITY", "MONITORING"]


def test_runtime_adapter_preserves_operation_error_isolation():
    opportunity = coordinator()
    monitoring = coordinator()

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=RuntimeError("opportunity failed"),
        ),
        patch.object(
            monitoring,
            "run",
            return_value=cycle_result(),
        ),
    ):
        adapter = ContinuousPaperOrchestrationRuntimeAdapter(
            opportunity_coordinator=opportunity,
            opportunity_input_factory=cycle_input,
            monitoring_coordinator=monitoring,
            monitoring_input_factory=cycle_input,
            config=ContinuousPaperOrchestrationRuntimeConfigV1(
                interval_seconds=0,
            ),
        )
        report = adapter.run_cycle()

    assert report["status"] == "COMPLETED_WITH_ERRORS"
    assert report["opportunity"]["status"] == "ERROR"
    assert report["monitoring"]["status"] == "COMPLETED"


def test_startup_failure_prevents_runtime_cycles():
    calls = []
    adapter = ContinuousPaperOrchestrationRuntimeAdapter(
        opportunity_coordinator=coordinator(),
        opportunity_input_factory=lambda: calls.append("O") or cycle_input(),
        monitoring_coordinator=coordinator(),
        monitoring_input_factory=lambda: calls.append("M") or cycle_input(),
        config=ContinuousPaperOrchestrationRuntimeConfigV1(
            interval_seconds=0,
        ),
        startup_operation=lambda: {
            "success": False,
            "error": "recovery failed",
        },
    )

    stats = adapter.run(max_cycles=1)

    assert stats["startup_status"] == "FAILED"
    assert calls == []
