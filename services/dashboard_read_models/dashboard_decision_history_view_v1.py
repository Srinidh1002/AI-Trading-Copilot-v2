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
class DashboardDecisionHistoryRowV1:
    source_id: str
    observed_at: datetime
    action: str
    confidence: float | None = None
    reference_price: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "observed_at",
            _aware(self.observed_at, "observed_at"),
        )
        object.__setattr__(self, "action", _text(self.action, "action"))
        object.__setattr__(
            self,
            "confidence",
            _optional_number(self.confidence, "confidence"),
        )
        object.__setattr__(
            self,
            "reference_price",
            _optional_number(self.reference_price, "reference_price"),
        )


@dataclass(frozen=True, slots=True)
class DashboardDecisionHistoryViewV1:
    source_id: str
    source_updated_at: datetime
    rows: tuple[DashboardDecisionHistoryRowV1, ...] = ()
    is_truncated: bool = False
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = (
        "dashboard_decision_history_view.v1"
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "source_updated_at",
            _aware(self.source_updated_at, "source_updated_at"),
        )
        if not isinstance(self.rows, tuple):
            raise TypeError("rows must be a tuple")
        if any(
            type(item) is not DashboardDecisionHistoryRowV1
            for item in self.rows
        ):
            raise TypeError("rows contains wrong type")
        if type(self.is_truncated) is not bool:
            raise TypeError("is_truncated must be a bool")
        object.__setattr__(
            self,
            "warnings",
            _diag(self.warnings, "warnings"),
        )
