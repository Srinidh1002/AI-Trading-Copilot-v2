from datetime import datetime, timezone
from unittest.mock import patch

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.paper_orchestration.existing_position_monitoring_cycle_executor import (
    ExistingPositionMonitoringCycleExecutor,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringInputV1,
    ExistingPositionMonitoringResultV1,
)


NOW = datetime(
    2026,
    1,
    8,
    9,
    30,
    tzinfo=timezone.utc,
)

HASH = "b" * 64


class EvaluationResultStub:
    evaluation_result_id = "evaluation-result-1"

    def to_json(self) -> str:
        return (
            '{"evaluation_result_id":'
            '"evaluation-result-1"}'
        )


class PortfolioSnapshotStub:
    portfolio_id = "portfolio-1"

    def to_json(self) -> str:
        return '{"portfolio_id":"portfolio-1"}'


def clock() -> datetime:
    return NOW


def cycle_input() -> PaperOrchestrationCycleInputV1:
    value = object.__new__(
        PaperOrchestrationCycleInputV1
    )

    object.__setattr__(
        value,
        "cycle_id",
        "monitor-cycle-1",
    )
    object.__setattr__(
        value,
        "cycle_idempotency_key",
        "monitor-cycle-key-1",
    )

    return value


def monitoring_input() -> ExistingPositionMonitoringInputV1:
    return object.__new__(
        ExistingPositionMonitoringInputV1
    )


def monitoring_result(
    status: str,
) -> ExistingPositionMonitoringResultV1:
    action_occurred = status in {
        "PARTIAL_EXIT",
        "CLOSED",
    }

    state_changed = status in {
        "HOLD_UPDATED",
        "PARTIAL_EXIT",
        "CLOSED",
    }

    value = object.__new__(
        ExistingPositionMonitoringResultV1
    )

    object.__setattr__(
        value,
        "status",
        status,
    )
    object.__setattr__(
        value,
        "evaluation_result",
        EvaluationResultStub(),
    )
    object.__setattr__(
        value,
        "p7_snapshot",
        object(),
    )
    object.__setattr__(
        value,
        "p8_snapshot",
        (
            PortfolioSnapshotStub()
            if state_changed
            else None
        ),
    )
    object.__setattr__(
        value,
        "p7_state_changed",
        state_changed,
    )
    object.__setattr__(
        value,
        "p8_state_changed",
        state_changed,
    )
    object.__setattr__(
        value,
        "paper_action_occurred",
        action_occurred,
    )
    object.__setattr__(
        value,
        "blockers",
        (
            ("BLOCKED_OBSERVATION",)
            if status == "BLOCKED"
            else ()
        ),
    )
    object.__setattr__(
        value,
        "decision_reasons",
        (),
    )
    object.__setattr__(
        value,
        "warnings",
        (),
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
        "existing_position_monitoring_result.v1",
    )

    return value


def execute(
    status: str,
):
    executor = ExistingPositionMonitoringCycleExecutor(
        monitoring_input_factory=(
            lambda cycle: monitoring_input()
        ),
        monitoring_authority=(
            lambda value: monitoring_result(status)
        ),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        return executor(cycle_input())


def test_blocked_monitoring_returns_blocked_cycle():
    result = execute("BLOCKED")

    assert result.cycle_status == "BLOCKED"
    assert result.terminal_stage == "P7_LIFECYCLE"
    assert result.blockers == (
        "BLOCKED_OBSERVATION",
    )
    assert result.paper_actions == ()


def test_hold_no_change_is_completed_no_action():
    result = execute("HOLD_NO_CHANGE")

    assert result.cycle_status == (
        "COMPLETED_NO_ACTION"
    )
    assert result.terminal_stage == "P7_LIFECYCLE"
    assert result.paper_actions == ()
    assert tuple(
        stage.stage
        for stage in result.stage_results
    ) == ("P7_LIFECYCLE",)


def test_hold_update_projects_p8_without_paper_action():
    result = execute("HOLD_UPDATED")

    assert result.cycle_status == (
        "COMPLETED_NO_ACTION"
    )
    assert result.terminal_stage == (
        "P8_PORTFOLIO_UPDATE"
    )
    assert result.paper_actions == ()
    assert tuple(
        stage.stage
        for stage in result.stage_results
    ) == (
        "P7_LIFECYCLE",
        "P8_PORTFOLIO_UPDATE",
    )


def test_partial_exit_reports_paper_action():
    result = execute("PARTIAL_EXIT")

    assert result.cycle_status == "COMPLETED"
    assert result.terminal_stage == (
        "P8_PORTFOLIO_UPDATE"
    )
    assert result.paper_actions == (
        "PARTIAL_EXIT_POSITION",
    )


def test_closed_reports_terminal_paper_action():
    result = execute("CLOSED")

    assert result.cycle_status == "COMPLETED"
    assert result.terminal_stage == (
        "P8_PORTFOLIO_UPDATE"
    )
    assert result.paper_actions == (
        "CLOSE_POSITION",
    )


def test_monitoring_exception_becomes_fail_closed_p7_stage():
    executor = ExistingPositionMonitoringCycleExecutor(
        monitoring_input_factory=(
            lambda cycle: (
                _ for _ in ()
            ).throw(
                RuntimeError("missing snapshot")
            )
        ),
        monitoring_authority=(
            lambda value: monitoring_result(
                "HOLD_NO_CHANGE"
            )
        ),
        clock=clock,
    )

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle_input())

    assert result.cycle_status == "FAILED"
    assert result.terminal_stage == "P7_LIFECYCLE"
    assert result.errors == (
        "P7_MONITORING_FAILURE",
    )
    assert (
        result.stage_results[-1]
        .failure
        .fail_closed
        is True
    )