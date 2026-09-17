"""Task 9-owned parent-evidence composition contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Task9ParentEvidenceDependenciesV1:
    """Provider/evidence composition used before the durable Task 9 child runtime.

    This object has no broker execution authority.  It may acquire certified
    market evidence and perform canonical parent/P6 planning only.
    """

    parent_cycle: Callable
    selected_planner: Callable

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not callable(self.parent_cycle):
            raise TypeError("parent_cycle")
        if not callable(self.selected_planner):
            raise TypeError("selected_planner")
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must remain PAPER")
        if self.broker_order_submission is not False:
            raise ValueError("broker submission must remain disabled")
        if self.live_execution_eligible is not False:
            raise ValueError("live execution must remain ineligible")
