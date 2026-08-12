"""Read-only analytical recommendation history; separate from PAPER trades."""
from __future__ import annotations

from typing import Any

from services.dashboard_read_models import DashboardApplicationViewV1
from services.dashboard_read_models.dashboard_decision_history_view_v1 import (
    DashboardDecisionHistoryRowV1,
)


def filter_recommendations(
    rows: tuple[DashboardDecisionHistoryRowV1, ...], *, action: str = "ALL",
) -> tuple[DashboardDecisionHistoryRowV1, ...]:
    if type(rows) is not tuple or any(type(item) is not DashboardDecisionHistoryRowV1 for item in rows):
        raise TypeError("rows")
    action = action.upper()
    if action not in {"ALL", "CALL", "PUT", "WAIT", "NO_TRADE"}:
        raise ValueError("action")
    return rows if action == "ALL" else tuple(item for item in rows if item.action.upper() == action)


def render_recommendation_history(*, st: Any, view: DashboardApplicationViewV1) -> None:
    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")
    st.subheader("RECOMMENDATION HISTORY")
    st.caption("Recommendation history is analytical history. It does not imply trade execution or Task 9 countability.")
    history = view.recommendation_history
    if history is None:
        st.info("Certified recommendation history has not been published.")
        return
    st.write(f"Source: {history.source_id} | Source updated: {history.source_updated_at.isoformat()}")
    if history.is_truncated:
        st.warning("Recommendation history is truncated; older published rows may be unavailable.")
    for warning in history.warnings:
        st.warning(f"History warning: {warning}")
    if not history.rows:
        st.info("No published recommendation rows are available.")
        return
    for row in history.rows:
        st.write(
            f"{row.observed_at.isoformat()} | Market: Unavailable | Action: {row.action} | "
            f"Confidence: {row.confidence if row.confidence is not None else 'Unavailable'} | "
            f"Reference price: {row.reference_price if row.reference_price is not None else 'Unavailable'} | Source/decision: {row.source_id}"
        )
