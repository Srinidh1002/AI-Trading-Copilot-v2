from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import aware, diagnostics, exact_tuple, paper_only, plain, text


@dataclass(frozen=True, slots=True)
class DashboardCycleViewV1:
    cycle_result_id: str
    cycle_id: str
    cycle_status: str
    terminal_stage: str
    started_at: datetime
    completed_at: datetime
    stage_statuses: tuple[tuple[str, str], ...]
    paper_actions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duplicate_of_cycle_result_id: str | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_cycle_view.v1"

    def __post_init__(self) -> None:
        for name in ("cycle_result_id", "cycle_id", "cycle_status", "terminal_stage"):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "started_at", aware(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", aware(self.completed_at, "completed_at"))
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        statuses = exact_tuple(self.stage_statuses, "stage_statuses")
        normalized = tuple((text(a, "stage"), text(b, "status")) for a, b in statuses)
        if len({name for name, _ in normalized}) != len(normalized):
            raise ValueError("duplicate stage status")
        object.__setattr__(self, "stage_statuses", normalized)
        for name in ("paper_actions", "blockers", "warnings", "errors"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))
        if self.duplicate_of_cycle_result_id is not None:
            object.__setattr__(
                self,
                "duplicate_of_cycle_result_id",
                text(self.duplicate_of_cycle_result_id, "duplicate_of_cycle_result_id"),
            )
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_cycle_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
