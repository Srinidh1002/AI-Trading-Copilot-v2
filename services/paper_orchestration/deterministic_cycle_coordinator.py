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
from services.contracts.paper_orchestration_failure_v1 import (
    PaperOrchestrationFailureV1,
)
from services.contracts.paper_orchestration_journal_record_v1 import (
    PaperOrchestrationJournalRecordV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


CycleExecutor = Callable[
    [PaperOrchestrationCycleInputV1],
    PaperOrchestrationCycleResultV1,
]


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise TypeError("clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value


class DeterministicPaperOrchestrationCycleCoordinator:
    """Idempotent, fail-closed wrapper around one PAPER cycle execution."""

    def __init__(self, *, journal, cycle_executor, clock) -> None:
        if type(journal) is not PaperOrchestrationJournal:
            raise TypeError("journal must be an exact PaperOrchestrationJournal")
        if not callable(cycle_executor):
            raise TypeError("cycle_executor must be callable")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.journal = journal
        self.cycle_executor = cycle_executor
        self.clock = clock

    @staticmethod
    def _validate_executor_result(*, cycle_input, cycle_result) -> None:
        if type(cycle_result) is not PaperOrchestrationCycleResultV1:
            raise TypeError(
                "cycle_executor must return an exact "
                "PaperOrchestrationCycleResultV1"
            )
        if cycle_result.cycle_id != cycle_input.cycle_id:
            raise ValueError("executor result cycle_id mismatch")
        if (
            cycle_result.cycle_idempotency_key
            != cycle_input.cycle_idempotency_key
        ):
            raise ValueError("executor result cycle idempotency mismatch")
        if (
            cycle_result.cycle_input_semantic_hash
            != cycle_input.semantic_hash()
        ):
            raise ValueError("executor result cycle input hash mismatch")
        if cycle_result.execution_mode != "PAPER":
            raise ValueError("executor result must be PAPER-only")
        if cycle_result.live_execution_eligible:
            raise ValueError("executor result must not be live eligible")

    def _duplicate_result(self, *, cycle_input, prior_raw, now):
        prior_result = prior_raw.get("cycle_result")
        if type(prior_result) is not dict:
            raise ValueError("stored orchestration cycle result is missing")
        prior_result_id = prior_result.get("cycle_result_id")
        if type(prior_result_id) is not str or not prior_result_id:
            raise ValueError("stored cycle result identity is missing")

        stage = PaperOrchestrationStageResultV1(
            stage_result_id=f"{cycle_input.cycle_id}:persistence:duplicate",
            cycle_id=cycle_input.cycle_id,
            stage="PERSISTENCE",
            status="DUPLICATE_NO_CHANGE",
            started_at=now,
            completed_at=now,
            source_result_type="PaperOrchestrationJournalRecordV1",
            source_result_id=prior_raw.get("journal_record_id"),
            source_semantic_hash=cycle_input.semantic_hash(),
            metadata={
                "duplicate_of_cycle_result_id": prior_result_id,
            },
        )
        return PaperOrchestrationCycleResultV1(
            cycle_result_id=f"{cycle_input.cycle_id}:duplicate-result",
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status="DUPLICATE_NO_CHANGE",
            terminal_stage="PERSISTENCE",
            started_at=now,
            completed_at=now,
            stage_results=(stage,),
            duplicate_of_cycle_result_id=prior_result_id,
            metadata={
                "journal_record_id": prior_raw.get("journal_record_id"),
            },
        )

    def _conflict_result(self, *, cycle_input, now):
        failure = PaperOrchestrationFailureV1(
            failure_code="IDEMPOTENCY_PAYLOAD_CONFLICT",
            stage="PERSISTENCE",
            message=(
                "cycle idempotency key is already bound to a "
                "different semantic payload"
            ),
            retryable=False,
            source_component=type(self).__name__,
        )
        stage = PaperOrchestrationStageResultV1(
            stage_result_id=f"{cycle_input.cycle_id}:persistence:conflict",
            cycle_id=cycle_input.cycle_id,
            stage="PERSISTENCE",
            status="FAILED",
            started_at=now,
            completed_at=now,
            errors=("IDEMPOTENCY_PAYLOAD_CONFLICT",),
            failure=failure,
        )
        return PaperOrchestrationCycleResultV1(
            cycle_result_id=f"{cycle_input.cycle_id}:conflict-result",
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status="FAILED",
            terminal_stage="PERSISTENCE",
            started_at=now,
            completed_at=now,
            stage_results=(stage,),
            errors=("IDEMPOTENCY_PAYLOAD_CONFLICT",),
        )

    def _executor_failure_result(
        self,
        *,
        cycle_input,
        started_at,
        completed_at,
        exc,
    ):
        failure = PaperOrchestrationFailureV1(
            failure_code="CYCLE_EXECUTOR_FAILURE",
            stage="PERSISTENCE",
            message=str(exc) or type(exc).__name__,
            retryable=False,
            exception_type=type(exc).__name__,
            source_component=type(self).__name__,
            metadata={"runtime_failure_stage": "RUNTIME"},
        )
        stage = PaperOrchestrationStageResultV1(
            stage_result_id=(
                f"{cycle_input.cycle_id}:persistence:executor-failure"
            ),
            cycle_id=cycle_input.cycle_id,
            stage="PERSISTENCE",
            status="FAILED",
            started_at=started_at,
            completed_at=completed_at,
            errors=("CYCLE_EXECUTOR_FAILURE",),
            failure=failure,
        )
        return PaperOrchestrationCycleResultV1(
            cycle_result_id=(
                f"{cycle_input.cycle_id}:executor-failure-result"
            ),
            cycle_id=cycle_input.cycle_id,
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=cycle_input.semantic_hash(),
            cycle_status="FAILED",
            terminal_stage="PERSISTENCE",
            started_at=started_at,
            completed_at=completed_at,
            stage_results=(stage,),
            errors=("CYCLE_EXECUTOR_FAILURE",),
        )

    def run(self, cycle_input):
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be an exact "
                "PaperOrchestrationCycleInputV1"
            )

        semantic_hash = cycle_input.semantic_hash()
        classification = self.journal.classify(
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=semantic_hash,
        )
        now = _aware_now(self.clock)

        if classification == "DUPLICATE_SAME_PAYLOAD":
            prior_raw = self.journal.get_raw(
                cycle_input.cycle_idempotency_key
            )
            if prior_raw is None:
                raise RuntimeError(
                    "journal duplicate classification lost its record"
                )
            return self._duplicate_result(
                cycle_input=cycle_input,
                prior_raw=prior_raw,
                now=now,
            )

        if classification == "IDEMPOTENCY_PAYLOAD_CONFLICT":
            return self._conflict_result(
                cycle_input=cycle_input,
                now=now,
            )

        started_at = now
        try:
            cycle_result = self.cycle_executor(cycle_input)
            self._validate_executor_result(
                cycle_input=cycle_input,
                cycle_result=cycle_result,
            )
        except Exception as exc:
            cycle_result = self._executor_failure_result(
                cycle_input=cycle_input,
                started_at=started_at,
                completed_at=_aware_now(self.clock),
                exc=exc,
            )

        record = PaperOrchestrationJournalRecordV1(
            journal_record_id=f"{cycle_input.cycle_id}:journal-record",
            cycle_idempotency_key=cycle_input.cycle_idempotency_key,
            cycle_input_semantic_hash=semantic_hash,
            cycle_result=cycle_result,
            persisted_at=_aware_now(self.clock),
        )
        self.journal.save(record)
        return cycle_result
