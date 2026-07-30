from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import (
    aware,
    diagnostics,
    exact_tuple,
    optional_number,
    paper_only,
    plain,
    text,
)
from .dashboard_paper_fill_view_v1 import DashboardPaperFillViewV1


@dataclass(frozen=True, slots=True)
class DashboardPaperPositionDetailViewV1:
    paper_trade_id: str
    position_id: str | None
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    lifecycle_state_id: str
    lifecycle_state: str
    lifecycle_display_group: str
    transition_sequence: int
    is_terminal: bool
    last_transition_code: str
    updated_at: datetime
    market: str | None = None
    exchange: str | None = None
    underlying_symbol: str | None = None
    option_symbol: str | None = None
    direction: str | None = None
    option_type: str | None = None
    strike: float | None = None
    expiry: str | None = None
    entry_price: float | None = None
    opened_at: datetime | None = None
    initial_lot_count: int | None = None
    lot_size: int | None = None
    initial_quantity: int | None = None
    remaining_lot_count: int | None = None
    remaining_quantity: int | None = None
    target_1_lot_count: int | None = None
    target_2_lot_count: int | None = None
    target_3_lot_count: int | None = None
    runner_lot_count: int | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    estimated_premium_outlay: float | None = None
    estimated_risk_amount: float | None = None
    estimated_total_trading_cost: float | None = None
    estimated_total_capital_requirement: float | None = None
    realized_net_pnl: float | None = None
    unrealized_pnl: float | None = None
    total_pnl: float | None = None
    current_option_price: float | None = None
    pnl_calculated_at: datetime | None = None
    fills: tuple[DashboardPaperFillViewV1, ...] = ()
    terminal_reason: str | None = None
    terminal_target: str | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_paper_position_detail_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "paper_trade_id",
            "trade_plan_id",
            "integrated_trade_plan_result_id",
            "lifecycle_state_id",
            "lifecycle_state",
            "lifecycle_display_group",
            "last_transition_code",
        ):
            object.__setattr__(self, name, text(getattr(self, name), name))
        for name in (
            "position_id",
            "market",
            "exchange",
            "underlying_symbol",
            "option_symbol",
            "direction",
            "option_type",
            "expiry",
            "terminal_reason",
            "terminal_target",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, text(value, name))
        if self.lifecycle_display_group not in {"PENDING", "ACTIVE", "TERMINAL", "BLOCKED"}:
            raise ValueError("unsupported lifecycle_display_group")
        if type(self.transition_sequence) is not int or isinstance(self.transition_sequence, bool):
            raise TypeError("transition_sequence must be an exact int")
        if self.transition_sequence < 0:
            raise ValueError("transition_sequence must be nonnegative")
        if type(self.is_terminal) is not bool:
            raise TypeError("is_terminal must be bool")
        object.__setattr__(self, "updated_at", aware(self.updated_at, "updated_at"))
        for name in ("opened_at", "pnl_calculated_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, aware(value, name))
        for name in (
            "initial_lot_count",
            "lot_size",
            "initial_quantity",
            "remaining_lot_count",
            "remaining_quantity",
            "target_1_lot_count",
            "target_2_lot_count",
            "target_3_lot_count",
            "runner_lot_count",
        ):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not int or isinstance(value, bool):
                    raise TypeError(f"{name} must be an exact int or None")
                if value < 0:
                    raise ValueError(f"{name} must be nonnegative")
        for name in (
            "strike",
            "entry_price",
            "stop_loss",
            "target_1",
            "target_2",
            "target_3",
            "estimated_premium_outlay",
            "estimated_risk_amount",
            "estimated_total_trading_cost",
            "estimated_total_capital_requirement",
            "realized_net_pnl",
            "unrealized_pnl",
            "total_pnl",
            "current_option_price",
        ):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        fills = exact_tuple(self.fills, "fills")
        if any(type(item) is not DashboardPaperFillViewV1 for item in fills):
            raise TypeError("fills contains wrong type")
        object.__setattr__(self, "fills", fills)
        for name in ("blockers", "warnings", "decision_reasons"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_paper_position_detail_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
