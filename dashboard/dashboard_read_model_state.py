from __future__ import annotations

from collections.abc import Mapping

from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanViewV1,
)


OPPORTUNITY_STATE_KEY = "dashboard_opportunity_view_v1"
TRADE_PLAN_STATE_KEY = "dashboard_trade_plan_view_v1"
PAPER_POSITION_STATE_KEY = "dashboard_paper_position_detail_view_v1"


def _optional_exact(
    state: Mapping[str, object],
    key: str,
    expected_type: type,
):
    value = state.get(key)
    if value is None:
        return None
    if type(value) is not expected_type:
        raise TypeError(
            f"{key} must contain exact {expected_type.__name__} or None"
        )
    return value


def get_plan_position_views(
    state: Mapping[str, object],
) -> tuple[
    DashboardOpportunityViewV1 | None,
    DashboardTradePlanViewV1 | None,
    DashboardPaperPositionDetailViewV1 | None,
]:
    """Read already-projected P6/P7 views from dashboard state."""

    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")

    return (
        _optional_exact(
            state,
            OPPORTUNITY_STATE_KEY,
            DashboardOpportunityViewV1,
        ),
        _optional_exact(
            state,
            TRADE_PLAN_STATE_KEY,
            DashboardTradePlanViewV1,
        ),
        _optional_exact(
            state,
            PAPER_POSITION_STATE_KEY,
            DashboardPaperPositionDetailViewV1,
        ),
    )
