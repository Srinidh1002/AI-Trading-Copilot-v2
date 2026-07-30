from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import aware, diagnostics, number, paper_only, plain, text


@dataclass(frozen=True, slots=True)
class DashboardPortfolioViewV1:
    portfolio_id: str
    trading_day_id: str
    updated_at: datetime
    starting_capital: float
    available_cash: float
    reserved_capital: float
    deployed_capital: float
    committed_capital: float
    realized_net_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_equity: float
    open_position_count: int
    pending_plan_count: int
    concurrent_trade_count: int
    aggregate_committed_risk: float
    event_sequence: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_portfolio_view.v1"

    def __post_init__(self) -> None:
        for name in ("portfolio_id", "trading_day_id"):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "updated_at", aware(self.updated_at, "updated_at"))
        for name in (
            "starting_capital",
            "available_cash",
            "reserved_capital",
            "deployed_capital",
            "committed_capital",
            "realized_net_pnl",
            "unrealized_pnl",
            "total_pnl",
            "total_equity",
            "aggregate_committed_risk",
        ):
            object.__setattr__(self, name, number(getattr(self, name), name))
        for name in (
            "open_position_count",
            "pending_plan_count",
            "concurrent_trade_count",
            "event_sequence",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        object.__setattr__(self, "blockers", diagnostics(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_portfolio_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
