from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module

from services.dashboard_read_models import (
    DashboardApplicationViewV1,
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanViewV1,
    build_task9_dashboard_shell_view,
    is_task9_dashboard_prepublication_shell,
    read_task9_external_provider_blocker,
)


OPPORTUNITY_STATE_KEY = "dashboard_opportunity_view_v1"
TRADE_PLAN_STATE_KEY = "dashboard_trade_plan_view_v1"
PAPER_POSITION_STATE_KEY = "dashboard_paper_position_detail_view_v1"
APPLICATION_VIEW_STATE_KEY = "dashboard_application_view_v1"


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


def get_application_view(
    state: Mapping[str, object],
) -> DashboardApplicationViewV1 | None:
    """Read the published unified application view without projection."""

    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")

    return _optional_exact(
        state,
        APPLICATION_VIEW_STATE_KEY,
        DashboardApplicationViewV1,
    )


def build_task9_prepublication_application_view(
) -> DashboardApplicationViewV1:
    """Obtain the safe Task 9 shell through the dashboard read boundary."""

    return build_task9_dashboard_shell_view()


def is_task9_prepublication_application_view(
    view: DashboardApplicationViewV1,
) -> bool:
    """Recognize the safe shell without exposing service details to pages."""

    return is_task9_dashboard_prepublication_shell(view)


def get_r4_paper_lifecycle_view(session_state):
    """Read the published R4 view through the certified state boundary."""

    from dashboard.r4_paper_lifecycle_components import (
        get_r4_paper_lifecycle_dashboard_view,
    )

    return get_r4_paper_lifecycle_dashboard_view(
        session_state
    )


def get_task9_external_provider_blocker_view(
    *,
    persistence_root,
    official_run_id,
):
    """Read-only Task 9 operator blocker projection for persistent dashboards."""

    return read_task9_external_provider_blocker(
        persistence_root=persistence_root,
        official_run_id=official_run_id,
    )


def recover_task9_durable_authorities(
    view: DashboardApplicationViewV1,
    *,
    persistence_root,
) -> DashboardApplicationViewV1:
    """Delegate durable recovery through the dashboard read-model boundary."""

    recovery_module = import_module(
        "services.dashboard_read_models.task9_durable_authority_recovery"
    )

    return recovery_module.recover_task9_durable_authorities(
        view,
        persistence_root=persistence_root,
    )