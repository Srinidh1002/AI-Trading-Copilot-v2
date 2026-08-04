from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from .dashboard_market_overview_view_v1 import (
    _aware,
    _diag,
    _optional_number,
    _text,
)


@dataclass(frozen=True, slots=True)
class DashboardComponentHealthViewV1:
    component: str
    status: str
    detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", _text(self.component, "component"))
        object.__setattr__(self, "status", _text(self.status, "status"))
        if self.detail is not None:
            object.__setattr__(self, "detail", _text(self.detail, "detail"))


@dataclass(frozen=True, slots=True)
class DashboardRuntimeOperationsViewV1:
    source_id: str
    runtime_status: str
    source_updated_at: datetime
    last_successful_cycle_at: datetime | None = None
    last_failed_attempt_at: datetime | None = None
    last_failed_attempt_error: str | None = None
    market_cycle_duration_seconds: float | None = None
    decision_cycle_duration_seconds: float | None = None
    freshness_status: str = "UNKNOWN"
    components: tuple[DashboardComponentHealthViewV1, ...] = ()
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = (
        "dashboard_runtime_operations_view.v1"
    )
    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "runtime_status": self.runtime_status,
            "source_updated_at": self.source_updated_at.isoformat(),
            "last_successful_cycle_at": (
                self.last_successful_cycle_at.isoformat()
                if self.last_successful_cycle_at is not None
                else None
            ),
            "last_failed_attempt_at": (
                self.last_failed_attempt_at.isoformat()
                if self.last_failed_attempt_at is not None
                else None
            ),
            "last_failed_attempt_error": self.last_failed_attempt_error,
            "market_cycle_duration_seconds": (
                self.market_cycle_duration_seconds
            ),
            "decision_cycle_duration_seconds": (
                self.decision_cycle_duration_seconds
            ),
            "freshness_status": self.freshness_status,
            "components": [
                {
                    "component": item.component,
                    "status": item.status,
                    "detail": item.detail,
                }
                for item in self.components
            ],
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }
    def __post_init__(self) -> None:
        for name in ("source_id", "runtime_status", "freshness_status"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "source_updated_at",
            _aware(self.source_updated_at, "source_updated_at"),
        )
        for name in (
            "last_successful_cycle_at",
            "last_failed_attempt_at",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _aware(value, name))
        if self.last_failed_attempt_error is not None:
            object.__setattr__(
                self,
                "last_failed_attempt_error",
                _text(
                    self.last_failed_attempt_error,
                    "last_failed_attempt_error",
                ),
            )
        for name in (
            "market_cycle_duration_seconds",
            "decision_cycle_duration_seconds",
        ):
            value = _optional_number(getattr(self, name), name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be nonnegative")
            object.__setattr__(self, name, value)
        if not isinstance(self.components, tuple):
            raise TypeError("components must be a tuple")
        if any(
            type(item) is not DashboardComponentHealthViewV1
            for item in self.components
        ):
            raise TypeError("components contains wrong type")
        object.__setattr__(
            self,
            "warnings",
            _diag(self.warnings, "warnings"),
        )
