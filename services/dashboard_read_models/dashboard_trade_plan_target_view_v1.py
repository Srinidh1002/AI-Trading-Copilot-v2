from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._shared import diagnostics, optional_number, plain, text


@dataclass(frozen=True, slots=True)
class DashboardTradePlanTargetViewV1:
    target_name: str
    target_price: float
    lot_count: int | None = None
    quantity: int | None = None
    reward_amount: float | None = None
    reward_to_risk: float | None = None
    booking_fraction: float | None = None
    warnings: tuple[str, ...] = ()
    schema_version: str = "dashboard_trade_plan_target_view.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_name", text(self.target_name, "target_name"))
        if self.target_name not in {"T1", "T2", "T3"}:
            raise ValueError("target_name must be T1, T2, or T3")
        target_price = optional_number(self.target_price, "target_price")
        if target_price is None or target_price <= 0:
            raise ValueError("target_price must be positive")
        object.__setattr__(self, "target_price", target_price)
        for name in ("lot_count", "quantity"):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not int or isinstance(value, bool):
                    raise TypeError(f"{name} must be an exact int or None")
                if value < 0:
                    raise ValueError(f"{name} must be nonnegative")
        for name in ("reward_amount", "reward_to_risk", "booking_fraction"):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        if self.booking_fraction is not None and not 0.0 <= self.booking_fraction <= 1.0:
            raise ValueError("booking_fraction must be between zero and one")
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        if self.schema_version != "dashboard_trade_plan_target_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
