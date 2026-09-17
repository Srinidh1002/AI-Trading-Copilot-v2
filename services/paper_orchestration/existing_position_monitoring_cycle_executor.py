from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringInputV1,
    ExistingPositionMonitoringResultV1,
)
from services.paper_orchestration.stage_result_factory import (
    build_completed_stage_result,
    build_failed_stage_result,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


MonitoringInputFactory = Callable[
    [PaperOrchestrationCycleInputV1],
    ExistingPositionMonitoringInputV1,
]
MonitoringAuthority = Callable[
    [ExistingPositionMonitoringInputV1],
    ExistingPositionMonitoringResultV1,
]


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise TypeError("clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value


class ExistingPositionMonitoringCycleExecutor:
    """Build an immutable P9 cycle result for one existing-position check."""

    def __init__(
        self,
        *,
        monitoring_input_factory: MonitoringInputFactory,
        monitoring_authority: MonitoringAuthority,
        clock: Clock,
    ) -> None:
        if not callable(monitoring_input_factory):
            raise TypeError("monitoring_input_factory must be callable")
        if not callable(monitoring_authority):
            raise TypeError("monitoring_authority must be callable")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.monitoring_input_factory = monitoring_input_factory
        self.monitoring_authority = monitoring_authority
        self.clock = clock

    def _result(
        self,
        *,
        cycle_input: PaperOrchestrationCycleInputV1,
        started_at: datetime,
        stage_results: list,
        cycle_status: str,
        paper_actions: tuple[str, ...] = (),
        blockers: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
    ) -> PaperOrchestrationCycleResultV1:
        return PaperOrchestrationCycleResultV1(
            cycle_result_id=f"{cycle_input.cycle_id}:monitoring-result",
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status=cycle_status,
            terminal_stage=stage_results[-1].stage,
            started_at=started_at,
            completed_at=_aware_now(self.clock),
            stage_results=tuple(stage_results),
            paper_actions=paper_actions,
            blockers=blockers,
            warnings=warnings,
            errors=errors,
            metadata={
                "executor": type(self).__name__,
                "scope": "EXISTING_POSITION_MONITORING",
            },
        )

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> PaperOrchestrationCycleResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )

        cycle_started_at = _aware_now(self.clock)
        p7_started_at = _aware_now(self.clock)

        try:
            monitoring_input = self.monitoring_input_factory(cycle_input)
            if type(monitoring_input) is not ExistingPositionMonitoringInputV1:
                raise TypeError(
                    "monitoring_input_factory must return exact "
                    "ExistingPositionMonitoringInputV1"
                )
            monitoring_result = self.monitoring_authority(
                monitoring_input
            )
            if type(monitoring_result) is not ExistingPositionMonitoringResultV1:
                raise TypeError(
                    "monitoring_authority must return exact "
                    "ExistingPositionMonitoringResultV1"
                )
        except Exception as exc:
            failure_code = "P7_MONITORING_FAILURE"
            failed = build_failed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:p7-lifecycle:failed"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P7_LIFECYCLE",
                started_at=p7_started_at,
                completed_at=_aware_now(self.clock),
                failure_code=failure_code,
                message=str(exc) or type(exc).__name__,
                retryable=False,
                source_component=type(self).__name__,
                exception=exc,
            )
            return self._result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=[failed],
                cycle_status="FAILED",
                errors=(failure_code,),
            )

        completed_at = _aware_now(self.clock)
        status = monitoring_result.status

        p7_stage_status = (
            "BLOCKED"
            if status == "BLOCKED"
            else "NO_ACTION"
            if status == "HOLD_NO_CHANGE"
            else "COMPLETED"
        )
        p7_stage = build_completed_stage_result(
            stage_result_id=(
                f"{cycle_input.cycle_id}:p7-lifecycle:"
                f"{p7_stage_status.lower()}"
            ),
            cycle_id=cycle_input.cycle_id,
            stage="P7_LIFECYCLE",
            started_at=p7_started_at,
            completed_at=completed_at,
            source_result=monitoring_result.evaluation_result,
            paper_action_occurred=(
                monitoring_result.paper_action_occurred
            ),
            blockers=monitoring_result.blockers,
            warnings=monitoring_result.warnings,
            status=p7_stage_status,
            metadata={
                "monitoring_status": status,
                "p7_state_changed": monitoring_result.p7_state_changed,
            },
        )
        stage_results = [p7_stage]

        if status == "BLOCKED":
            return self._result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="BLOCKED",
                blockers=monitoring_result.blockers,
                warnings=monitoring_result.warnings,
            )

        if status == "HOLD_NO_CHANGE":
            return self._result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="COMPLETED_NO_ACTION",
                warnings=monitoring_result.warnings,
            )

        p8_stage = build_completed_stage_result(
            stage_result_id=(
                f"{cycle_input.cycle_id}:p8-portfolio-update:completed"
            ),
            cycle_id=cycle_input.cycle_id,
            stage="P8_PORTFOLIO_UPDATE",
            started_at=p7_started_at,
            completed_at=completed_at,
            source_result=monitoring_result.p8_snapshot,
            paper_action_occurred=(
                monitoring_result.paper_action_occurred
            ),
            warnings=monitoring_result.warnings,
            metadata={
                "monitoring_status": status,
                "p8_state_changed": monitoring_result.p8_state_changed,
            },
        )
        stage_results.append(p8_stage)

        if status == "HOLD_UPDATED":
            return self._result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="COMPLETED_NO_ACTION",
                warnings=monitoring_result.warnings,
            )

        action = (
            "PARTIAL_EXIT_POSITION"
            if status == "PARTIAL_EXIT"
            else "CLOSE_POSITION"
        )
        return self._result(
            cycle_input=cycle_input,
            started_at=cycle_started_at,
            stage_results=stage_results,
            cycle_status="COMPLETED",
            paper_actions=(action,),
            warnings=monitoring_result.warnings,
        )
