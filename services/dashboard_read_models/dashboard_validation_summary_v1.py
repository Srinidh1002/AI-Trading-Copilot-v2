from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._shared import diagnostics, number, optional_number, plain, text


@dataclass(frozen=True, slots=True)
class DashboardValidationSummaryV1:
    completed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    breakeven_trade_count: int
    gross_pnl: float
    net_pnl: float
    win_rate_fraction: float
    average_win: float | None
    average_loss: float | None
    profit_factor: float | None
    maximum_win: float | None
    maximum_loss: float | None
    data_status: str
    warnings: tuple[str, ...] = ()
    schema_version: str = "dashboard_validation_summary.v1"

    def __post_init__(self) -> None:
        for name in (
            "completed_trade_count",
            "winning_trade_count",
            "losing_trade_count",
            "breakeven_trade_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if (
            self.winning_trade_count
            + self.losing_trade_count
            + self.breakeven_trade_count
            != self.completed_trade_count
        ):
            raise ValueError("trade counts are inconsistent")
        object.__setattr__(self, "gross_pnl", number(self.gross_pnl, "gross_pnl"))
        object.__setattr__(self, "net_pnl", number(self.net_pnl, "net_pnl"))
        object.__setattr__(self, "win_rate_fraction", number(self.win_rate_fraction, "win_rate_fraction"))
        if not 0.0 <= self.win_rate_fraction <= 1.0:
            raise ValueError("win_rate_fraction must be between zero and one")
        for name in ("average_win", "average_loss", "profit_factor", "maximum_win", "maximum_loss"):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        object.__setattr__(self, "data_status", text(self.data_status, "data_status"))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        if self.schema_version != "dashboard_validation_summary.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
