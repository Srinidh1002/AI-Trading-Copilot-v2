from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import aware, diagnostics, optional_number, paper_only, plain, text


@dataclass(frozen=True, slots=True)
class DashboardPaperPositionViewV1:
    paper_trade_id: str
    trade_plan_id: str
    lifecycle_state: str
    updated_at: datetime
    position_id: str | None = None
    market: str | None = None
    instrument: str | None = None
    entry_price: float | None = None
    remaining_quantity: int = 0
    realized_net_pnl: float | None = None
    unrealized_pnl: float | None = None
    total_pnl: float | None = None
    event_sequence: int = 0
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_paper_position_view.v1"

    def __post_init__(self) -> None:
        for name in ("paper_trade_id", "trade_plan_id", "lifecycle_state"):
            object.__setattr__(self, name, text(getattr(self, name), name))
        for name in ("position_id", "market", "instrument"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, text(value, name))
        object.__setattr__(self, "updated_at", aware(self.updated_at, "updated_at"))
        for name in ("entry_price", "realized_net_pnl", "unrealized_pnl", "total_pnl"):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        if type(self.remaining_quantity) is not int or isinstance(self.remaining_quantity, bool):
            raise TypeError("remaining_quantity must be an exact int")
        if self.remaining_quantity < 0:
            raise ValueError("remaining_quantity must be nonnegative")
        if type(self.event_sequence) is not int or isinstance(self.event_sequence, bool):
            raise TypeError("event_sequence must be an exact int")
        if self.event_sequence < 0:
            raise ValueError("event_sequence must be nonnegative")
        object.__setattr__(self, "blockers", diagnostics(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_paper_position_view.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
