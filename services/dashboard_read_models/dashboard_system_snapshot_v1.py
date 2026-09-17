from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ._shared import aware, diagnostics, exact_tuple, paper_only, plain, text
from .dashboard_cycle_view_v1 import DashboardCycleViewV1
from .dashboard_market_state_v1 import DashboardMarketStateV1
from .dashboard_paper_position_view_v1 import DashboardPaperPositionViewV1
from .dashboard_portfolio_view_v1 import DashboardPortfolioViewV1
from .dashboard_runner_health_v1 import DashboardRunnerHealthV1
from .dashboard_validation_summary_v1 import DashboardValidationSummaryV1


@dataclass(frozen=True, slots=True)
class DashboardSystemSnapshotV1:
    snapshot_id: str
    generated_at: datetime
    market_states: tuple[DashboardMarketStateV1, ...]
    positions: tuple[DashboardPaperPositionViewV1, ...]
    runner_health: DashboardRunnerHealthV1
    validation_summary: DashboardValidationSummaryV1
    latest_cycle: DashboardCycleViewV1 | None = None
    portfolio: DashboardPortfolioViewV1 | None = None
    system_status: str = "NO_DATA"
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "dashboard_system_snapshot.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "generated_at", aware(self.generated_at, "generated_at"))
        markets = exact_tuple(self.market_states, "market_states")
        if any(type(item) is not DashboardMarketStateV1 for item in markets):
            raise TypeError("market_states contains wrong type")
        if len({item.market for item in markets}) != len(markets):
            raise ValueError("duplicate market state")
        positions = exact_tuple(self.positions, "positions")
        if any(type(item) is not DashboardPaperPositionViewV1 for item in positions):
            raise TypeError("positions contains wrong type")
        if len({item.paper_trade_id for item in positions}) != len(positions):
            raise ValueError("duplicate paper trade")
        if type(self.runner_health) is not DashboardRunnerHealthV1:
            raise TypeError("runner_health has wrong type")
        if type(self.validation_summary) is not DashboardValidationSummaryV1:
            raise TypeError("validation_summary has wrong type")
        if self.latest_cycle is not None and type(self.latest_cycle) is not DashboardCycleViewV1:
            raise TypeError("latest_cycle has wrong type")
        if self.portfolio is not None and type(self.portfolio) is not DashboardPortfolioViewV1:
            raise TypeError("portfolio has wrong type")
        object.__setattr__(self, "system_status", text(self.system_status, "system_status"))
        for name in ("blockers", "warnings", "errors"):
            object.__setattr__(self, name, diagnostics(getattr(self, name), name))
        paper_only(self.execution_mode, self.live_execution_eligible)
        if self.schema_version != "dashboard_system_snapshot.v1":
            raise ValueError("unsupported schema_version")

    def to_dict(self) -> dict[str, Any]:
        return {name: plain(getattr(self, name)) for name in self.__dataclass_fields__}
