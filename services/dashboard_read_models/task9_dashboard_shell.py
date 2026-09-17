"""Safe pre-publication shell for the read-only Task 9 dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

from .dashboard_application_view_v1 import DashboardApplicationViewV1


_SHELL_VIEW_ID = "task9-dashboard-shell-v1"
_SHELL_SESSION_STATE = "NOT_YET_PUBLISHED"


def build_task9_dashboard_shell_view() -> DashboardApplicationViewV1:
    """Return navigation-only UI state with no market or progress claims."""

    return DashboardApplicationViewV1(
        view_id=_SHELL_VIEW_ID,
        generated_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        market_session_state=_SHELL_SESSION_STATE,
        blockers=("NO_CERTIFIED_LIVE_PUBLICATION_YET",),
        warnings=(
            "Task 9 dashboard is read-only and awaits the first certified publication.",
        ),
    )


def is_task9_dashboard_prepublication_shell(
    view: DashboardApplicationViewV1,
) -> bool:
    """Identify typed shell state without treating its timestamp as evidence."""

    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")
    return (
        view.view_id == _SHELL_VIEW_ID
        and view.market_session_state == _SHELL_SESSION_STATE
    )
