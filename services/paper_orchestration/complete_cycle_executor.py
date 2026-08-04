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
from services.paper_orchestration.complete_cycle_execution_context import (
    CompleteCycleAuthoritySetV1,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
    NewEntryPaperLifecycleResultV1,
)
from services.paper_orchestration.p6_planning_stage_executor import (
    P6PlanningStageInputV1,
    execute_p6_planning_stage,
)
from services.paper_orchestration.stage_result_factory import (
    build_completed_stage_result,
    build_failed_stage_result,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


P6StageAuthority = Callable[
    [P6PlanningStageInputV1],
    object,
]
NewEntryStageAuthority = Callable[
    [NewEntryPaperLifecycleInputV1],
    NewEntryPaperLifecycleResultV1,
]


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise TypeError("clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value


def _tuple_text(value: object, name: str) -> tuple[str, ...]:
    candidate = getattr(value, name, ())
    if candidate is None:
        return ()
    return tuple(str(item) for item in candidate if str(item).strip())


def _status(value: object, *names: str) -> str:
    for name in names:
        candidate = getattr(value, name, None)
        if candidate is not None:
            return str(candidate).strip().upper()
    return ""


class CompletePaperOrchestrationCycleExecutor:
    """Run one deterministic PAPER opportunity/new-entry cycle.

    The journal/idempotency coordinator remains the outer boundary.
    Existing-position monitoring is added by the next WP3 batch.
    """

    def __init__(
        self,
        *,
        authorities: CompleteCycleAuthoritySetV1,
        new_entry_stage_authority: NewEntryStageAuthority,
        clock: Clock,
        p6_stage_authority: P6StageAuthority = execute_p6_planning_stage,
    ) -> None:
        if type(authorities) is not CompleteCycleAuthoritySetV1:
            raise TypeError(
                "authorities must be exact CompleteCycleAuthoritySetV1"
            )
        if not callable(new_entry_stage_authority):
            raise TypeError("new_entry_stage_authority must be callable")
        if not callable(p6_stage_authority):
            raise TypeError("p6_stage_authority must be callable")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.authorities = authorities
        self.new_entry_stage_authority = new_entry_stage_authority
        self.p6_stage_authority = p6_stage_authority
        self.clock = clock

    def _cycle_result(
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
        completed_at = _aware_now(self.clock)
        return PaperOrchestrationCycleResultV1(
            cycle_result_id=f"{cycle_input.cycle_id}:cycle-result",
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status=cycle_status,
            terminal_stage=stage_results[-1].stage,
            started_at=started_at,
            completed_at=completed_at,
            stage_results=tuple(stage_results),
            paper_actions=paper_actions,
            blockers=blockers,
            warnings=warnings,
            errors=errors,
            metadata={
                "executor": type(self).__name__,
                "scope": "OPPORTUNITY_AND_NEW_ENTRY",
            },
        )

    def _run_authority_stage(
        self,
        *,
        cycle_input: PaperOrchestrationCycleInputV1,
        stage: str,
        authority: Callable,
        args: tuple,
        stage_results: list,
    ) -> object | PaperOrchestrationCycleResultV1:
        started_at = _aware_now(self.clock)
        try:
            source_result = authority(*args)
        except Exception as exc:
            completed_at = _aware_now(self.clock)
            failure_code = f"{stage}_AUTHORITY_FAILURE"
            stage_results.append(
                build_failed_stage_result(
                    stage_result_id=(
                        f"{cycle_input.cycle_id}:{stage.lower()}:failed"
                    ),
                    cycle_id=cycle_input.cycle_id,
                    stage=stage,
                    started_at=started_at,
                    completed_at=completed_at,
                    failure_code=failure_code,
                    message=str(exc) or type(exc).__name__,
                    retryable=False,
                    source_component=getattr(
                        authority,
                        "__name__",
                        type(authority).__name__,
                    ),
                    exception=exc,
                )
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=stage_results[0].started_at,
                stage_results=stage_results,
                cycle_status="FAILED",
                errors=(failure_code,),
            )

        completed_at = _aware_now(self.clock)
        stage_results.append(
            build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:{stage.lower()}:completed"
                ),
                cycle_id=cycle_input.cycle_id,
                stage=stage,
                started_at=started_at,
                completed_at=completed_at,
                source_result=source_result,
                blockers=_tuple_text(source_result, "blockers"),
                warnings=_tuple_text(source_result, "warnings"),
            )
        )
        return source_result

    def __call__(
        self,
        cycle_input: PaperOrchestrationCycleInputV1,
    ) -> PaperOrchestrationCycleResultV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact PaperOrchestrationCycleInputV1"
            )

        cycle_started_at = _aware_now(self.clock)
        stage_results: list = []

        data_result = self._run_authority_stage(
            cycle_input=cycle_input,
            stage="DATA",
            authority=self.authorities.data_authority,
            args=(cycle_input,),
            stage_results=stage_results,
        )
        if type(data_result) is PaperOrchestrationCycleResultV1:
            return data_result

        session_result = self._run_authority_stage(
            cycle_input=cycle_input,
            stage="SESSION",
            authority=self.authorities.session_authority,
            args=(cycle_input, data_result),
            stage_results=stage_results,
        )
        if type(session_result) is PaperOrchestrationCycleResultV1:
            return session_result

        if not bool(getattr(session_result, "analysis_allowed", False)):
            stage_results[-1] = build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:session:blocked"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="SESSION",
                started_at=stage_results[-1].started_at,
                completed_at=stage_results[-1].completed_at,
                source_result=session_result,
                blockers=_tuple_text(session_result, "blockers")
                or ("SESSION_NOT_ACTIONABLE",),
                warnings=_tuple_text(session_result, "warnings"),
                status="BLOCKED",
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="BLOCKED",
                blockers=stage_results[-1].blockers,
                warnings=stage_results[-1].warnings,
            )

        analysis_result = self._run_authority_stage(
            cycle_input=cycle_input,
            stage="ANALYSIS",
            authority=self.authorities.analysis_authority,
            args=(cycle_input, data_result, session_result),
            stage_results=stage_results,
        )
        if type(analysis_result) is PaperOrchestrationCycleResultV1:
            return analysis_result

        opportunity_result = self._run_authority_stage(
            cycle_input=cycle_input,
            stage="OPPORTUNITY",
            authority=self.authorities.opportunity_authority,
            args=(cycle_input, analysis_result, session_result),
            stage_results=stage_results,
        )
        if type(opportunity_result) is PaperOrchestrationCycleResultV1:
            return opportunity_result

        opportunity_status = _status(
            opportunity_result,
            "opportunity_status",
            "status",
        )
        opportunity_blockers = _tuple_text(
            opportunity_result,
            "blockers",
        )
        opportunity_warnings = _tuple_text(
            opportunity_result,
            "warnings",
        )

        if opportunity_status == "NO_ACTION":
            stage_results[-1] = build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:opportunity:no-action"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="OPPORTUNITY",
                started_at=stage_results[-1].started_at,
                completed_at=stage_results[-1].completed_at,
                source_result=opportunity_result,
                warnings=opportunity_warnings,
                status="NO_ACTION",
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="COMPLETED_NO_ACTION",
                warnings=opportunity_warnings,
            )

        if opportunity_status in {"BLOCKED", "CONFLICTING"}:
            stage_results[-1] = build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:opportunity:blocked"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="OPPORTUNITY",
                started_at=stage_results[-1].started_at,
                completed_at=stage_results[-1].completed_at,
                source_result=opportunity_result,
                blockers=opportunity_blockers
                or ("OPPORTUNITY_NOT_READY",),
                warnings=opportunity_warnings,
                status="BLOCKED",
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="BLOCKED",
                blockers=stage_results[-1].blockers,
                warnings=opportunity_warnings,
            )

        if opportunity_status == "FAILED":
            failure_code = "OPPORTUNITY_RESULT_FAILED"
            failed = build_failed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:opportunity:failed-result"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="OPPORTUNITY",
                started_at=stage_results[-1].started_at,
                completed_at=stage_results[-1].completed_at,
                failure_code=failure_code,
                message="opportunity authority returned FAILED",
                retryable=False,
                source_component=type(opportunity_result).__name__,
            )
            stage_results[-1] = failed
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="FAILED",
                errors=(failure_code,),
            )

        p6_input = self.authorities.p6_input_factory(
            cycle_input,
            analysis_result,
            opportunity_result,
        )
        p6_result = self._run_authority_stage(
            cycle_input=cycle_input,
            stage="P6_PLAN",
            authority=self.p6_stage_authority,
            args=(p6_input,),
            stage_results=stage_results,
        )
        if type(p6_result) is PaperOrchestrationCycleResultV1:
            return p6_result

        p6_status = _status(p6_result, "status")
        if p6_status != "READY":
            blockers = _tuple_text(p6_result, "blockers")
            warnings = _tuple_text(p6_result, "warnings")
            terminal_status = (
                "BLOCKED"
                if p6_status in {"BLOCKED", "FAILED"}
                else "NO_ACTION"
            )
            stage_results[-1] = build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:p6-plan:"
                    f"{terminal_status.lower()}"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P6_PLAN",
                started_at=stage_results[-1].started_at,
                completed_at=stage_results[-1].completed_at,
                source_result=p6_result,
                blockers=blockers,
                warnings=warnings,
                status=terminal_status,
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status=(
                    "BLOCKED"
                    if terminal_status == "BLOCKED"
                    else "COMPLETED_NO_ACTION"
                ),
                blockers=blockers,
                warnings=warnings,
            )

        new_entry_input = self.authorities.new_entry_input_factory(
            cycle_input,
            p6_result,
        )
        lifecycle_started_at = _aware_now(self.clock)
        try:
            lifecycle_result = self.new_entry_stage_authority(
                new_entry_input
            )
        except Exception as exc:
            completed_at = _aware_now(self.clock)
            failure_code = "NEW_ENTRY_LIFECYCLE_FAILURE"
            stage_results.append(
                build_failed_stage_result(
                    stage_result_id=(
                        f"{cycle_input.cycle_id}:p8-admission:failed"
                    ),
                    cycle_id=cycle_input.cycle_id,
                    stage="P8_ADMISSION",
                    started_at=lifecycle_started_at,
                    completed_at=completed_at,
                    failure_code=failure_code,
                    message=str(exc) or type(exc).__name__,
                    retryable=False,
                    source_component=getattr(
                        self.new_entry_stage_authority,
                        "__name__",
                        type(self.new_entry_stage_authority).__name__,
                    ),
                    exception=exc,
                )
            )
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="FAILED",
                errors=(failure_code,),
            )

        lifecycle_completed_at = _aware_now(self.clock)
        lifecycle_status = lifecycle_result.status

        admission_status = (
            "BLOCKED"
            if lifecycle_status == "ADMISSION_BLOCKED"
            else "NO_ACTION"
            if lifecycle_status == "NO_CAPACITY"
            else "COMPLETED"
        )
        stage_results.append(
            build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:p8-admission:"
                    f"{admission_status.lower()}"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P8_ADMISSION",
                started_at=lifecycle_started_at,
                completed_at=lifecycle_completed_at,
                source_result=lifecycle_result.admission_result,
                blockers=lifecycle_result.blockers,
                warnings=lifecycle_result.warnings,
                status=admission_status,
            )
        )

        if lifecycle_status == "ADMISSION_BLOCKED":
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="BLOCKED",
                blockers=lifecycle_result.blockers,
                warnings=lifecycle_result.warnings,
            )

        if lifecycle_status == "NO_CAPACITY":
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="COMPLETED_NO_ACTION",
                warnings=lifecycle_result.warnings,
            )

        p7_status = (
            "BLOCKED"
            if lifecycle_status == "ENTRY_BLOCKED"
            else "NO_ACTION"
            if lifecycle_status in {
                "WAITING_FOR_ENTRY",
                "ENTRY_CLOSED",
            }
            else "COMPLETED"
        )
        stage_results.append(
            build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:p7-lifecycle:"
                    f"{p7_status.lower()}"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P7_LIFECYCLE",
                started_at=lifecycle_started_at,
                completed_at=lifecycle_completed_at,
                source_result=lifecycle_result.entry_result,
                paper_action_occurred=(
                    lifecycle_status == "OPEN"
                ),
                blockers=lifecycle_result.blockers,
                warnings=lifecycle_result.warnings,
                status=p7_status,
            )
        )

        if lifecycle_status == "ENTRY_BLOCKED":
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="BLOCKED",
                blockers=lifecycle_result.blockers,
                warnings=lifecycle_result.warnings,
            )

        if lifecycle_status in {"WAITING_FOR_ENTRY", "ENTRY_CLOSED"}:
            return self._cycle_result(
                cycle_input=cycle_input,
                started_at=cycle_started_at,
                stage_results=stage_results,
                cycle_status="COMPLETED_NO_ACTION",
                warnings=lifecycle_result.warnings,
            )

        if lifecycle_status != "OPEN":
            raise ValueError(
                "new-entry lifecycle returned unsupported status"
            )

        stage_results.append(
            build_completed_stage_result(
                stage_result_id=(
                    f"{cycle_input.cycle_id}:p8-portfolio-update:"
                    "completed"
                ),
                cycle_id=cycle_input.cycle_id,
                stage="P8_PORTFOLIO_UPDATE",
                started_at=lifecycle_started_at,
                completed_at=lifecycle_completed_at,
                source_result=lifecycle_result.p8_snapshot,
                paper_action_occurred=True,
                warnings=lifecycle_result.warnings,
            )
        )
        return self._cycle_result(
            cycle_input=cycle_input,
            started_at=cycle_started_at,
            stage_results=stage_results,
            cycle_status="COMPLETED",
            paper_actions=("OPEN_POSITION",),
            warnings=lifecycle_result.warnings,
        )
