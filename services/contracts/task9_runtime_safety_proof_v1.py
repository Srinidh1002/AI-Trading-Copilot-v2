"""Task 9 runtime/PAPER safety proof contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9RuntimeSafetyStatus(str, Enum):
    READY = "READY"
    EMERGENCY_HALTED = "EMERGENCY_HALTED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class Task9RuntimeSafetyProofV1:
    proof_id: str
    observed_at: datetime
    status: Task9RuntimeSafetyStatus

    runtime_config_id: str
    execution_mode: str
    broker_order_submission: bool
    live_execution_eligible: bool

    repository_broker: str
    repository_paper_trading_enabled: bool
    repository_live_trading_enabled: bool

    repository_paper_safety_passed: bool
    no_broker_submission_guard_passed: bool

    emergency_halt_enabled: bool
    emergency_halt_reason: str | None

    new_entries_permitted: bool
    monitoring_permitted: bool

    sanitized_reason: str | None = None

    schema_version: str = (
        "task9_runtime_safety_proof.v1"
    )

    def __post_init__(self) -> None:
        if (
            type(self.proof_id) is not str
            or not self.proof_id.strip()
        ):
            raise ValueError("proof_id")

        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at")

        if (
            type(self.runtime_config_id) is not str
            or not self.runtime_config_id.strip()
        ):
            raise ValueError("runtime_config_id")

        for name in (
            "broker_order_submission",
            "live_execution_eligible",
            "repository_paper_trading_enabled",
            "repository_live_trading_enabled",
            "repository_paper_safety_passed",
            "no_broker_submission_guard_passed",
            "emergency_halt_enabled",
            "new_entries_permitted",
            "monitoring_permitted",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode")

        if self.broker_order_submission is not False:
            raise ValueError(
                "broker_order_submission"
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "live_execution_eligible"
            )

        if self.emergency_halt_enabled:
            if (
                type(self.emergency_halt_reason) is not str
                or not self.emergency_halt_reason.strip()
            ):
                raise ValueError(
                    "emergency_halt_reason"
                )

            if self.new_entries_permitted:
                raise ValueError(
                    "halted runtime cannot permit entries"
                )

        if self.monitoring_permitted is not True:
            raise ValueError(
                "Task 9 safety proof must preserve monitoring"
            )

        if self.status is Task9RuntimeSafetyStatus.READY:
            if not (
                self.repository_paper_safety_passed
                and self.no_broker_submission_guard_passed
            ):
                raise ValueError(
                    "READY safety proof missing guard proof"
                )

            if self.emergency_halt_enabled:
                raise ValueError(
                    "READY cannot be emergency halted"
                )

            if self.new_entries_permitted is not True:
                raise ValueError(
                    "READY must permit PAPER entries"
                )

            if self.sanitized_reason is not None:
                raise ValueError(
                    "READY safety reason"
                )

        elif self.status is Task9RuntimeSafetyStatus.EMERGENCY_HALTED:
            if not self.emergency_halt_enabled:
                raise ValueError(
                    "halt status without halt"
                )

            if self.sanitized_reason is None:
                raise ValueError(
                    "halted safety reason"
                )

        elif self.status is Task9RuntimeSafetyStatus.INVALID:
            if self.sanitized_reason is None:
                raise ValueError(
                    "invalid safety reason"
                )


__all__ = (
    "Task9RuntimeSafetyProofV1",
    "Task9RuntimeSafetyStatus",
)
