from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
from .dashboard_trade_plan_target_view_v1 import DashboardTradePlanTargetViewV1


@dataclass(frozen=True, slots=True)
class DashboardTradePlanViewV1:
    trade_plan_id: str
    selected_opportunity_id: str
    evaluated_at: datetime
    underlying_symbol: str
    exchange: str
    market: str
    plan_status: str
    direction: str
    instrument_type: str
    opportunity_confidence: float
    option_confidence: float | None
    plan_confidence: float
    selected_option_contract_id: str | None = None
    selected_option_symbol: str | None = None
    strike: float | None = None
    option_type: str | None = None
    entry_zone_lower: float | None = None
    entry_zone_upper: float | None = None
    entry_reference_price: float | None = None
    entry_tolerance_fraction: float | None = None
    maximum_chase_price: float | None = None
    entry_method: str | None = None
    stop_loss_price: float | None = None
    stop_loss_method: str | None = None
    stop_distance: float | None = None
    stop_distance_fraction: float | None = None
    targets: tuple[DashboardTradePlanTargetViewV1, ...] = ()
    lot_size: int | None = None
    lot_count: int | None = None
    quantity: int | None = None
    available_capital: float | None = None
    required_capital: float | None = None
    risk_amount: float | None = None
    maximum_permissible_loss: float | None = None
    estimated_entry_cost: float | None = None
    estimated_exit_cost: float | None = None
    estimated_total_charges: float | None = None
    estimated_slippage_cost: float | None = None
    expiry: date | None = None
    days_to_expiry: int | None = None
    expiry_category: str | None = None
    invalidation_rules: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_trade_plan_view.v1"

    def __post_init__(self) -> None:
        for name in (
            "trade_plan_id",
            "selected_opportunity_id",
            "underlying_symbol",
            "exchange",
            "market",
            "plan_status",
            "direction",
            "instrument_type",
        ):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", aware(self.evaluated_at, "evaluated_at"))
        for name in (
            "selected_option_contract_id",
            "selected_option_symbol",
            "option_type",
            "entry_method",
            "stop_loss_method",
            "expiry_category",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, text(value, name))
        if self.expiry is not None:
            if isinstance(self.expiry, datetime) or not isinstance(self.expiry, date):
                raise TypeError("expiry must be a date or None")
        for name in ("lot_size", "lot_count", "quantity", "days_to_expiry"):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not int or isinstance(value, bool):
                    raise TypeError(f"{name} must be an exact int or None")
                if value < 0:
                    raise ValueError(f"{name} must be nonnegative")
        for name in (
            "opportunity_confidence",
            "option_confidence",
            "plan_confidence",
            "strike",
            "entry_zone_lower",
            "entry_zone_upper",
            "entry_reference_price",
            "entry_tolerance_fraction",
            "maximum_chase_price",
            "stop_loss_price",
            "stop_distance",
            "stop_distance_fraction",
            "available_capital",
            "required_capital",
            "risk_amount",
            "maximum_permissible_loss",
            "estimated_entry_cost",
            "estimated_exit_cost",
            "estimated_total_charges",
            "estimated_slippage_cost",
        ):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        for name in ("opportunity_confidence", "plan_confidence"):
            if getattr(self, name) is None:
                raise ValueError(f"{name} is required")
        targets = exact_tuple(self.targets, "targets")
        if any(type(item) is not DashboardTradePlanTargetViewV1 for item in targets):
            raise TypeError("targets contains wrong type")
        expected = ("T1", "T2", "T3")
        actual = tuple(item.target_name for item in targets)
        if targets and actual != expected:
            raise ValueError("targets must be ordered exactly as T1, T2, T3")
        object.__setattr__(self, "targets", targets)
        for name in ("invalidation_rules", "blockers", "warnings", "decision_reasons"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))
        if self.plan_status == "READY":
            if self.blockers:
                raise ValueError("READY plan cannot contain blockers")
            if len(self.targets) != 3:
                raise ValueError("READY plan requires three targets")
        if self.plan_status == "BLOCKED" and not self.blockers:
            raise ValueError("BLOCKED plan requires blockers")
        if self.plan_status == "NO_TRADE" and not self.decision_reasons:
            raise ValueError("NO_TRADE plan requires decision reasons")
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_trade_plan_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
