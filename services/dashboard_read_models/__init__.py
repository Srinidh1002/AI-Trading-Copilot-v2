"""Immutable PAPER-only dashboard read-model contracts."""

from .dashboard_cycle_view_v1 import DashboardCycleViewV1
from .dashboard_market_state_v1 import DashboardMarketStateV1
from .dashboard_opportunity_view_v1 import DashboardOpportunityViewV1
from .dashboard_paper_fill_view_v1 import DashboardPaperFillViewV1
from .dashboard_paper_position_detail_view_v1 import (
    DashboardPaperPositionDetailViewV1,
)
from .dashboard_paper_position_view_v1 import DashboardPaperPositionViewV1
from .dashboard_plan_position_projection_adapters import (
    project_paper_trade_fill,
    project_paper_trade_position_detail,
    project_three_target_trade_plan,
    project_trade_opportunity,
)
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
from .dashboard_trade_plan_target_view_v1 import (
    DashboardTradePlanTargetViewV1,
)
from .dashboard_trade_plan_view_v1 import DashboardTradePlanViewV1
from .dashboard_validation_summary_v1 import DashboardValidationSummaryV1

__all__ = [
    "DashboardCycleViewV1",
    "DashboardMarketStateV1",
    "DashboardOpportunityViewV1",
    "DashboardPaperFillViewV1",
    "DashboardPaperPositionDetailViewV1",
    "DashboardPaperPositionViewV1",
    "DashboardPortfolioViewV1",
    "DashboardReadModelAssembler",
    "DashboardReadModelAssemblyInputV1",
    "DashboardRunnerHealthV1",
    "DashboardSystemSnapshotV1",
    "DashboardTradePlanTargetViewV1",
    "DashboardTradePlanViewV1",
    "DashboardValidationSummaryV1",
    "project_cycle_result",
    "project_paper_trade_fill",
    "project_paper_trade_position_detail",
    "project_paper_trade_snapshot",
    "project_portfolio_snapshot",
    "project_runtime_stats",
    "project_three_target_trade_plan",
    "project_trade_opportunity",
]
