from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import aware, diagnostics, number, plain, text


@dataclass(frozen=True, slots=True)
class DashboardPaperFillViewV1:
    fill_id: str
    fill_type: str
    fill_reason: str
    side: str
    filled_lot_count: int
    lot_size: int
    filled_quantity: int
    fill_price: float
    gross_notional: float
    estimated_trading_cost: float
    net_cash_effect: float
    filled_at: datetime
    source: str
    target_name: str | None = None
    warnings: tuple[str, ...] = ()
    schema_version: str = "dashboard_paper_fill_view.v1"

    def __post_init__(self) -> None:
        for name in ("fill_id", "fill_type", "fill_reason", "side", "source"):
            object.__setattr__(self, name, text(getattr(self, name), name))
        if self.target_name is not None:
            object.__setattr__(self, "target_name", text(self.target_name, "target_name"))
        for name in ("filled_lot_count", "lot_size", "filled_quantity"):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool):
                raise TypeError(f"{name} must be an exact int")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "fill_price",
            "gross_notional",
            "estimated_trading_cost",
            "net_cash_effect",
        ):
            object.__setattr__(self, name, number(getattr(self, name), name))
        object.__setattr__(self, "filled_at", aware(self.filled_at, "filled_at"))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        if self.schema_version != "dashboard_paper_fill_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
