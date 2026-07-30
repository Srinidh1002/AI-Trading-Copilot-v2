"""Immutable PAPER-only dashboard read-model contracts."""

from .dashboard_cycle_view_v1 import DashboardCycleViewV1
from .dashboard_market_state_v1 import DashboardMarketStateV1
from .dashboard_paper_position_view_v1 import DashboardPaperPositionViewV1
from .dashboard_portfolio_view_v1 import DashboardPortfolioViewV1
from .dashboard_projection_adapters import (
    project_cycle_result,
    project_paper_trade_snapshot,
    project_portfolio_snapshot,
    project_runtime_stats,
)
from .dashboard_read_model_assembler import (
    DashboardReadModelAssembler,
    DashboardReadModelAssemblyInputV1,
)
from .dashboard_runner_health_v1 import DashboardRunnerHealthV1
from .dashboard_system_snapshot_v1 import DashboardSystemSnapshotV1
from .dashboard_validation_summary_v1 import DashboardValidationSummaryV1

__all__ = [
    "DashboardCycleViewV1",
    "DashboardMarketStateV1",
    "DashboardPaperPositionViewV1",
    "DashboardPortfolioViewV1",
    "DashboardReadModelAssembler",
    "DashboardReadModelAssemblyInputV1",
    "DashboardRunnerHealthV1",
    "DashboardSystemSnapshotV1",
    "DashboardValidationSummaryV1",
    "project_cycle_result",
    "project_paper_trade_snapshot",
    "project_portfolio_snapshot",
    "project_runtime_stats",
]
