from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._shared import diagnostics, optional_number, paper_only, plain, text


@dataclass(frozen=True, slots=True)
class DashboardRunnerHealthV1:
    running: bool
    stop_requested: bool
    interrupted: bool
    startup_status: str
    cycles_started: int
    cycles_completed: int
    cycles_with_errors: int
    opportunity_successes: int
    opportunity_failures: int
    monitoring_successes: int
    monitoring_failures: int
    startup_error: str | None = None
    last_cycle_status: str | None = None
    last_cycle_number: int | None = None
    last_cycle_duration_seconds: float | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_runner_health.v1"

    def __post_init__(self) -> None:
        for name in ("running", "stop_requested", "interrupted"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        object.__setattr__(self, "startup_status", text(self.startup_status, "startup_status"))
        for name in (
            "cycles_started",
            "cycles_completed",
            "cycles_with_errors",
            "opportunity_successes",
            "opportunity_failures",
            "monitoring_successes",
            "monitoring_failures",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        for name in ("startup_error", "last_cycle_status"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, text(value, name))
        if self.last_cycle_number is not None:
            if type(self.last_cycle_number) is not int or isinstance(self.last_cycle_number, bool):
                raise TypeError("last_cycle_number must be an exact int")
            if self.last_cycle_number < 0:
                raise ValueError("last_cycle_number must be nonnegative")
        object.__setattr__(
            self,
            "last_cycle_duration_seconds",
            optional_number(self.last_cycle_duration_seconds, "last_cycle_duration_seconds"),
        )
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        object.__setattr__(self, "errors", diagnostics(self.errors, "errors"))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_runner_health.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
