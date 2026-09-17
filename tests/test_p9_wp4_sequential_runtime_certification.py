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


def coordinator() -> DeterministicPaperOrchestrationCycleCoordinator:
    return object.__new__(
        DeterministicPaperOrchestrationCycleCoordinator
    )


def cycle_input(
    *,
    cycle_id: str,
    idempotency_key: str,
) -> PaperOrchestrationCycleInputV1:
    value = object.__new__(PaperOrchestrationCycleInputV1)
    object.__setattr__(value, "cycle_id", cycle_id)
    object.__setattr__(
        value,
        "cycle_idempotency_key",
        idempotency_key,
    )
    return value


def cycle_result(
    value: PaperOrchestrationCycleInputV1,
    *,
    status: str = "COMPLETED_NO_ACTION",
) -> PaperOrchestrationCycleResultV1:
    result = object.__new__(PaperOrchestrationCycleResultV1)

    object.__setattr__(
        result,
        "cycle_result_id",
        f"{value.cycle_id}:result",
    )
    object.__setattr__(
        result,
        "cycle_id",
        value.cycle_id,
    )
    object.__setattr__(
        result,
        "cycle_idempotency_key",
        value.cycle_idempotency_key,
    )
    object.__setattr__(
        result,
        "cycle_input_semantic_hash",
        "a" * 64,
    )
    object.__setattr__(
        result,
        "cycle_status",
        status,
    )
    object.__setattr__(
        result,
        "terminal_stage",
        "PERSISTENCE",
    )
    object.__setattr__(
        result,
        "started_at",
        NOW,
    )
    object.__setattr__(
        result,
        "completed_at",
        NOW,
    )
    object.__setattr__(
        result,
        "stage_results",
        (),
    )
    object.__setattr__(
        result,
        "paper_actions",
        (),
    )
    object.__setattr__(
        result,
        "blockers",
        (),
    )
    object.__setattr__(
        result,
        "warnings",
        (),
    )
    object.__setattr__(
        result,
        "errors",
        (),
    )
    object.__setattr__(
        result,
        "duplicate_of_cycle_result_id",
        None,
    )
    object.__setattr__(
        result,
        "metadata",
        {},
    )
    object.__setattr__(
        result,
        "execution_mode",
        "PAPER",
    )
    object.__setattr__(
        result,
        "live_execution_eligible",
        False,
    )
    object.__setattr__(
        result,
        "schema_version",
        "paper_orchestration_cycle_result.v1",
    )

    return result


class InputSequence:
    def __init__(self, lane: str) -> None:
        self.lane = lane
        self.sequence = 0
        self.created: list[PaperOrchestrationCycleInputV1] = []

    def __call__(self) -> PaperOrchestrationCycleInputV1:
        self.sequence += 1
        value = cycle_input(
            cycle_id=f"{self.lane}-cycle-{self.sequence}",
            idempotency_key=(
                f"{self.lane}-cycle-key-{self.sequence}"
            ),
        )
        self.created.append(value)
        return value


def build_adapter(
    *,
    opportunity,
    monitoring,
    opportunity_factory,
    monitoring_factory,
) -> ContinuousPaperOrchestrationRuntimeAdapter:
    return ContinuousPaperOrchestrationRuntimeAdapter(
        opportunity_coordinator=opportunity,
        opportunity_input_factory=opportunity_factory,
        monitoring_coordinator=monitoring,
        monitoring_input_factory=monitoring_factory,
        config=ContinuousPaperOrchestrationRuntimeConfigV1(
            interval_seconds=0,
        ),
        sleep_function=lambda value: None,
        monotonic_function=lambda: 1.0,
    )


def test_two_runtime_cycles_preserve_locked_lane_order():
    order = []
    opportunity = coordinator()
    monitoring = coordinator()
    opportunity_inputs = InputSequence("opportunity")
    monitoring_inputs = InputSequence("monitoring")

    def run_opportunity(value):
        order.append(("OPPORTUNITY", value.cycle_id))
        return cycle_result(value)

    def run_monitoring(value):
        order.append(("MONITORING", value.cycle_id))
        return cycle_result(value)

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=run_opportunity,
        ),
        patch.object(
            monitoring,
            "run",
            side_effect=run_monitoring,
        ),
    ):
        adapter = build_adapter(
            opportunity=opportunity,
            monitoring=monitoring,
            opportunity_factory=opportunity_inputs,
            monitoring_factory=monitoring_inputs,
        )
        adapter.run(max_cycles=2)

    assert order == [
        ("OPPORTUNITY", "opportunity-cycle-1"),
        ("MONITORING", "monitoring-cycle-1"),
        ("OPPORTUNITY", "opportunity-cycle-2"),
        ("MONITORING", "monitoring-cycle-2"),
    ]


def test_sequential_cycles_use_distinct_caller_supplied_identities():
    opportunity = coordinator()
    monitoring = coordinator()
    opportunity_inputs = InputSequence("opportunity")
    monitoring_inputs = InputSequence("monitoring")

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=cycle_result,
        ),
        patch.object(
            monitoring,
            "run",
            side_effect=cycle_result,
        ),
    ):
        adapter = build_adapter(
            opportunity=opportunity,
            monitoring=monitoring,
            opportunity_factory=opportunity_inputs,
            monitoring_factory=monitoring_inputs,
        )
        adapter.run(max_cycles=3)

    all_inputs = (
        opportunity_inputs.created
        + monitoring_inputs.created
    )
    cycle_ids = [value.cycle_id for value in all_inputs]
    keys = [
        value.cycle_idempotency_key
        for value in all_inputs
    ]

    assert len(cycle_ids) == 6
    assert len(set(cycle_ids)) == 6
    assert len(set(keys)) == 6


def test_one_opportunity_failure_does_not_suppress_monitoring_or_next_cycle():
    order = []
    opportunity = coordinator()
    monitoring = coordinator()
    opportunity_inputs = InputSequence("opportunity")
    monitoring_inputs = InputSequence("monitoring")
    opportunity_attempt = 0

    def run_opportunity(value):
        nonlocal opportunity_attempt
        opportunity_attempt += 1
        order.append(
            ("OPPORTUNITY", opportunity_attempt)
        )

        if opportunity_attempt == 1:
            raise RuntimeError(
                "first opportunity failed"
            )

        return cycle_result(value)

    def run_monitoring(value):
        order.append(
            ("MONITORING", value.cycle_id)
        )
        return cycle_result(value)

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=run_opportunity,
        ),
        patch.object(
            monitoring,
            "run",
            side_effect=run_monitoring,
        ),
    ):
        adapter = build_adapter(
            opportunity=opportunity,
            monitoring=monitoring,
            opportunity_factory=opportunity_inputs,
            monitoring_factory=monitoring_inputs,
        )
        adapter.run(max_cycles=2)

    assert order == [
        ("OPPORTUNITY", 1),
        ("MONITORING", "monitoring-cycle-1"),
        ("OPPORTUNITY", 2),
        ("MONITORING", "monitoring-cycle-2"),
    ]
    assert opportunity_attempt == 2
    assert opportunity_inputs.sequence == 2
    assert monitoring_inputs.sequence == 2


def test_cycle_results_remain_paper_only_across_repeated_runtime_execution():
    captured = []
    opportunity = coordinator()
    monitoring = coordinator()
    opportunity_inputs = InputSequence("opportunity")
    monitoring_inputs = InputSequence("monitoring")

    def execute(value):
        result = cycle_result(value)
        captured.append(result)
        return result

    with (
        patch.object(
            opportunity,
            "run",
            side_effect=execute,
        ),
        patch.object(
            monitoring,
            "run",
            side_effect=execute,
        ),
    ):
        adapter = build_adapter(
            opportunity=opportunity,
            monitoring=monitoring,
            opportunity_factory=opportunity_inputs,
            monitoring_factory=monitoring_inputs,
        )
        adapter.run(max_cycles=2)

    assert len(captured) == 4
    assert all(
        result.execution_mode == "PAPER"
        for result in captured
    )
    assert all(
        result.live_execution_eligible is False
        for result in captured
    )