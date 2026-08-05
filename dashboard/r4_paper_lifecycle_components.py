"""Read-only Streamlit rendering for certified R4 PAPER lifecycle state."""

from __future__ import annotations

from typing import Any, Mapping

from services.dashboard_read_models.r4_paper_lifecycle_dashboard_view_v1 import (
    R4PaperLifecycleDashboardViewV1,
    build_r4_paper_lifecycle_dashboard_view,
)


R4_PAPER_LIFECYCLE_VIEW_STATE_KEY = (
    "r4_paper_lifecycle_dashboard_view.v1"
)


def publish_r4_paper_lifecycle_dashboard_view(
    session_state: Mapping[str, Any] | Any,
    view: R4PaperLifecycleDashboardViewV1,
) -> None:
    """Publish an immutable view into Streamlit session state."""

    if type(view) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "view must be exact "
            "R4PaperLifecycleDashboardViewV1"
        )

    session_state[R4_PAPER_LIFECYCLE_VIEW_STATE_KEY] = view


def get_r4_paper_lifecycle_dashboard_view(
    session_state: Mapping[str, Any] | Any,
) -> R4PaperLifecycleDashboardViewV1 | None:
    value = session_state.get(
        R4_PAPER_LIFECYCLE_VIEW_STATE_KEY
    )

    if value is None:
        return None

    if type(value) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "published R4 dashboard state has invalid type"
        )

    return value


def _money(value: float) -> str:
    return f"₹{value:,.2f}"


def render_r4_paper_lifecycle_dashboard(
    st: Any,
    view: R4PaperLifecycleDashboardViewV1,
) -> None:
    """Render certified state without triggering any mutation."""

    if type(view) is not R4PaperLifecycleDashboardViewV1:
        raise TypeError(
            "view must be exact "
            "R4PaperLifecycleDashboardViewV1"
        )

    st.subheader("PAPER Portfolio Lifecycle")

    st.caption(
        "Read-only persisted P7/P8 lifecycle state. "
        "No orders or state changes can be triggered here."
    )

    state_col, reservation_col, restart_col, reconcile_col = (
        st.columns(4)
    )

    state_col.metric("Lifecycle", view.lifecycle_state)
    reservation_col.metric("Reservation", view.reservation_status)
    restart_col.metric("Restart", view.restart_status)
    reconcile_col.metric("Reconciliation", view.reconciliation_status)

    symbol_col, quantity_col, entry_col, current_col = st.columns(4)

    symbol_col.metric("Contract", view.option_symbol)
    quantity_col.metric(
        "Quantity",
        f"{view.remaining_quantity} / {view.initial_quantity}",
    )
    entry_col.metric("Entry Price", f"{view.entry_price:.2f}")
    current_col.metric(
        "Current Price",
        (
            "Unavailable"
            if view.current_option_price is None
            else f"{view.current_option_price:.2f}"
        ),
    )

    realized_col, unrealized_col, total_col = st.columns(3)

    realized_col.metric(
        "Realized P&L",
        _money(view.realized_net_pnl),
    )
    unrealized_col.metric(
        "Unrealized P&L",
        _money(view.unrealized_pnl),
    )
    total_col.metric("Total P&L", _money(view.total_pnl))

    capital_col, risk_col, duplicate_col = st.columns(3)

    capital_col.metric(
        "Remaining Capital",
        _money(view.remaining_capital_amount),
    )
    risk_col.metric(
        "Remaining Risk",
        _money(view.remaining_risk_amount),
    )
    duplicate_col.metric(
        "Duplicate Protection",
        (
            "VERIFIED"
            if view.duplicate_protection_verified
            else "NOT VERIFIED"
        ),
    )

    st.write(
        {
            "portfolio_id": view.portfolio_id,
            "paper_trade_id": view.paper_trade_id,
            "position_id": view.position_id,
            "underlying_symbol": view.underlying_symbol,
            "latest_observation_id": view.latest_observation_id,
            "latest_observation_at": (
                None
                if view.latest_observation_at is None
                else view.latest_observation_at.isoformat()
            ),
            "entry_fill_id": view.entry_fill_id,
            "exit_fill_ids": list(view.exit_fill_ids),
            "updated_at": (
                None
                if view.updated_at is None
                else view.updated_at.isoformat()
            ),
            "execution_mode": view.execution_mode,
            "live_execution_eligible": view.live_execution_eligible,
        }
    )

    if view.reconciliation_drift_codes:
        st.error(
            "Reconciliation drift detected: "
            + ", ".join(view.reconciliation_drift_codes)
        )
    else:
        st.success(
            "Persisted position, reservation, quantities, "
            "fills, capital, risk, and P&L are reconciled."
        )
