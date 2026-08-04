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
class DashboardValidationSummaryViewV1:
    source_id: str
    source_updated_at: datetime
    total_completed_trades: int
    winning_trades: int
    losing_trades: int
    net_realized_pnl: float
    warnings: tuple[str, ...] = ()

    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False
    schema_version: ClassVar[str] = (
        "dashboard_validation_summary_view.v1"
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "source_updated_at",
            _aware(self.source_updated_at, "source_updated_at"),
        )
        for name in (
            "total_completed_trades",
            "winning_trades",
            "losing_trades",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if (
            self.winning_trades + self.losing_trades
            > self.total_completed_trades
        ):
            raise ValueError(
                "wins plus losses cannot exceed completed trades"
            )
        object.__setattr__(
            self,
            "net_realized_pnl",
            _optional_number(
                self.net_realized_pnl,
                "net_realized_pnl",
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            _diag(self.warnings, "warnings"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_updated_at": self.source_updated_at.isoformat(),
            "total_completed_trades": self.total_completed_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "net_realized_pnl": self.net_realized_pnl,
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }
