"""Sanitized durable diagnostics for the Task 9 PAPER launcher."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9LauncherDiagnosticCategory(str, Enum):
    ATTEMPT_STARTED = "ATTEMPT_STARTED"
    CYCLE_COMPLETED = "CYCLE_COMPLETED"
    SESSION_CLOSED = "SESSION_CLOSED"
    INTERRUPTED = "INTERRUPTED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"
    RUN_COMPLETED = "RUN_COMPLETED"


class Task9LauncherDiagnosticStage(str, Enum):
    PRE_LOOP = "PRE_LOOP"
    BEFORE_CYCLE = "BEFORE_CYCLE"
    RUN_CYCLE = "RUN_CYCLE"
    AFTER_CYCLE = "AFTER_CYCLE"
    SLEEP = "SLEEP"
    TERMINATION = "TERMINATION"


@dataclass(frozen=True, slots=True)
class Task9LauncherRuntimeDiagnosticV1:
    diagnostic_id: str
    official_run_id: str
    observed_at: datetime
    attempt_number: int
    completed_cycles: int
    stage: Task9LauncherDiagnosticStage
    category: Task9LauncherDiagnosticCategory
    reason_code: str
    graceful_shutdown: bool
    exception_class: str | None = None
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "task9_launcher_runtime_diagnostic.v1"

    def __post_init__(self) -> None:
        for name in ("diagnostic_id", "official_run_id", "reason_code"):
            if type(getattr(self, name)) is not str or not getattr(self, name).strip():
                raise ValueError(name)
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at")
        if type(self.attempt_number) is not int or self.attempt_number < 0:
            raise ValueError("attempt_number")
        if type(self.completed_cycles) is not int or self.completed_cycles < 0:
            raise ValueError("completed_cycles")
        object.__setattr__(self, "stage", Task9LauncherDiagnosticStage(self.stage))
        object.__setattr__(self, "category", Task9LauncherDiagnosticCategory(self.category))
        if self.exception_class is not None and (type(self.exception_class) is not str or not self.exception_class.isidentifier() or len(self.exception_class) > 80):
            raise ValueError("exception_class")
        if self.execution_mode != "PAPER" or self.broker_order_submission is not False or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only launcher diagnostic")

    def to_dict(self) -> dict[str, object]:
        return {"diagnostic_id": self.diagnostic_id, "official_run_id": self.official_run_id, "observed_at": self.observed_at.isoformat(), "attempt_number": self.attempt_number, "completed_cycles": self.completed_cycles, "stage": self.stage.value, "category": self.category.value, "reason_code": self.reason_code, "graceful_shutdown": self.graceful_shutdown, "exception_class": self.exception_class, "execution_mode": "PAPER", "broker_order_submission": False, "live_execution_eligible": False, "schema_version": self.schema_version}
