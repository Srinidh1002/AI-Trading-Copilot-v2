"""Typed active-position discovery and restart recovery result."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)


_RECOVERY_STATUSES = {"NO_ACTIVE_POSITION", "RECOVERED", "BLOCKED"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class PaperPositionRecoveryResultV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_position_recovery_result.v1"

    recovery_result_id: str
    recovery_cycle_id: str
    evaluated_at: datetime
    status: str
    discovered_position_count: int
    recovered_position: ActivePaperPositionV1 | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("recovery_result_id", "recovery_cycle_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        status = _text(self.status, "status").upper()
        if status not in _RECOVERY_STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        if (
            type(self.discovered_position_count) is not int
            or self.discovered_position_count < 0
        ):
            raise ValueError("discovered_position_count")
        if (
            self.recovered_position is not None
            and type(self.recovered_position)
            is not ActivePaperPositionV1
        ):
            raise TypeError("recovered_position")

        object.__setattr__(
            self,
            "blockers",
            _messages(self.blockers, "blockers"),
        )
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )

        if status == "NO_ACTIVE_POSITION":
            if (
                self.discovered_position_count != 0
                or self.recovered_position is not None
                or self.blockers
            ):
                raise ValueError("NO_ACTIVE_POSITION coherence")
        elif status == "RECOVERED":
            if (
                self.discovered_position_count != 1
                or self.recovered_position is None
                or self.blockers
            ):
                raise ValueError("RECOVERED coherence")
        else:
            if not self.blockers or self.recovered_position is not None:
                raise ValueError("BLOCKED coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only recovery result")
