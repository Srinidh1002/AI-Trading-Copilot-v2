"""Typed end-to-end PAPER lifecycle runtime result."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.active_paper_position_v1 import ActivePaperPositionV1
from services.contracts.paper_monitoring_lifecycle_v1 import PaperLifecycleTransitionV1
from services.contracts.paper_position_recovery_result_v1 import PaperPositionRecoveryResultV1
from services.contracts.paper_trade_finalization_v1 import PaperTradeFinalizationResultV1


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class PaperLifecycleRuntimeResultV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_lifecycle_runtime_result.v1"

    runtime_result_id: str
    runtime_cycle_id: str
    evaluated_at: datetime
    status: str
    recovery_result: PaperPositionRecoveryResultV1
    transition: PaperLifecycleTransitionV1 | None
    position_before: ActivePaperPositionV1 | None
    position_after: ActivePaperPositionV1 | None
    finalization_result: PaperTradeFinalizationResultV1 | None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("runtime_result_id", "runtime_cycle_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        if self.status not in {"NO_ACTIVE_POSITION", "APPLIED", "BLOCKED"}:
            raise ValueError("status")
        if type(self.recovery_result) is not PaperPositionRecoveryResultV1:
            raise TypeError("recovery_result")
        if self.transition is not None and type(self.transition) is not PaperLifecycleTransitionV1:
            raise TypeError("transition")
        for name in ("position_before", "position_after"):
            value = getattr(self, name)
            if value is not None and type(value) is not ActivePaperPositionV1:
                raise TypeError(name)
        if self.finalization_result is not None and type(self.finalization_result) is not PaperTradeFinalizationResultV1:
            raise TypeError("finalization_result")

        if self.status == "NO_ACTIVE_POSITION":
            if any(
                value is not None
                for value in (
                    self.transition,
                    self.position_before,
                    self.position_after,
                    self.finalization_result,
                )
            ):
                raise ValueError("NO_ACTIVE_POSITION coherence")
        elif self.status == "BLOCKED":
            if self.position_after is not None or self.finalization_result is not None:
                raise ValueError("BLOCKED coherence")
        else:
            if (
                self.transition is None
                or self.position_before is None
                or self.position_after is None
            ):
                raise ValueError("APPLIED coherence")
            if self.transition.action in {
                "TARGET_3_HIT",
                "EXIT_NOW",
                "STOP_HIT",
                "TRADE_CLOSED",
            }:
                if self.position_after.lifecycle_state != "CLOSED":
                    raise ValueError("terminal runtime result must close position")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only runtime result")
