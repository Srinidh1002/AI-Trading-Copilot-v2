from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import (
    aware,
    diagnostics,
    optional_number,
    paper_only,
    plain,
    text,
)


@dataclass(frozen=True, slots=True)
class DashboardMarketStateV1:
    market: str
    symbol: str
    observed_at: datetime
    market_status: str
    data_status: str
    freshness_status: str
    ltp: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_market_state.v1"

    def __post_init__(self) -> None:
        for name in ("market", "symbol", "market_status", "data_status", "freshness_status"):
            object.__setattr__(self, name, text(getattr(self, name), name))
        object.__setattr__(self, "observed_at", aware(self.observed_at, "observed_at"))
        for name in ("ltp", "open", "high", "low", "close", "volume"):
            object.__setattr__(self, name, optional_number(getattr(self, name), name))
        object.__setattr__(self, "warnings", diagnostics(self.warnings, "warnings"))
        object.__setattr__(self, "blockers", diagnostics(self.blockers, "blockers"))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_market_state.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
