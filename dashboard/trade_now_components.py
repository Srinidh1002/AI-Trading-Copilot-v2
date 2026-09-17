"""Read-only first-screen renderer for published Task 9 recommendations."""
from __future__ import annotations

from typing import Any

from services.dashboard_read_models import (
    DashboardApplicationViewV1,
)
from dashboard.dashboard_read_model_state import (
    is_task9_prepublication_application_view,
)


def render_trade_now_dashboard(*, st: Any, view: DashboardApplicationViewV1) -> None:
    """Render only already-published immutable recommendation data."""
    if st is None:
        raise TypeError("st")
    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")

    st.subheader("Trade Now")
    st.caption("PAPER CERTIFICATION ACTIVE")
    st.info("PAPER ONLY · NO REAL ORDER WILL BE SENT · BROKER ORDER SUBMISSION DISABLED")
    if view.active_paper_position is not None:
        _render_active_paper_position(st, view)
        st.subheader("ORIGINAL RECOMMENDATION (REFERENCE)")
        _render_recommendation_details(st, view)
        return
    st.subheader("PRIMARY RECOMMENDATION")

    status, actionable = _display_status(view)
    plan = view.primary_trade_plan
    opportunity = view.primary_opportunity
    action = _first(
        getattr(plan, "option_type", None),
        getattr(opportunity, "option_type", None),
        getattr(opportunity, "action", None),
        getattr(plan, "plan_status", None),
        "Unavailable",
    )
    confidence = _first(
        getattr(plan, "plan_confidence", None),
        getattr(opportunity, "decision_confidence", None),
    )
    selected_col, action_col, status_col, confidence_col = st.columns(4)
    selected_col.metric("Selected Market", view.selected_market or "NONE")
    action_col.metric("Action", action)
    status_col.metric("Status", status)
    confidence_col.metric("Confidence", _value(confidence))

    if not actionable:
        st.warning("Published recommendation is non-actionable. Inspect it for reference only.")
    _render_recommendation_details(st, view)

    st.subheader("NIFTY vs SENSEX")
    nifty_col, sensex_col = st.columns(2)
    _render_market_card(nifty_col, "NIFTY", view.nifty_market, view.selected_market)
    _render_market_card(sensex_col, "SENSEX", view.sensex_market, view.selected_market)

    st.subheader(f"SELECTED MARKET → {view.selected_market or 'NONE'}")
    _render_messages(st, "Why selected", view.selected_market_rationale)
    _render_messages(st, "Why not the other market", view.rejected_market_rationale)
    st.caption(f"Evaluated/generated: {_generated_at_label(view)}")


def _generated_at_label(view: DashboardApplicationViewV1) -> str:
    if is_task9_prepublication_application_view(view):
        return "Not yet published"
    return view.generated_at.isoformat()


def _render_active_paper_position(
    st: Any,
    view: DashboardApplicationViewV1,
) -> None:
    position = view.active_paper_position
    if position is None:
        return
    heading = "POSITION CLOSED" if position.is_terminal else "ACTIVE PAPER POSITION"
    st.subheader(heading)
    st.info("PAPER POSITION · NO REAL ORDER WILL BE SENT · BROKER SUBMISSION DISABLED")
    if _position_reference_only(view):
        st.warning("Last published position state shown for reference only; lifecycle guidance is non-actionable.")
    elif position.is_terminal:
        st.warning("This PAPER position is terminal and is not currently actionable.")

    one, two, three, four = st.columns(4)
    one.metric("Market", _value(position.market))
    one.metric("Contract", _value(position.option_symbol))
    two.metric("Lifecycle", position.lifecycle_state)
    two.metric("Published transition", position.last_transition_code)
    three.metric("Entry", _value(position.entry_price))
    three.metric("Current Premium", _value(position.current_option_price))
    four.metric("Remaining Quantity", _value(position.remaining_quantity))
    four.metric("Transition Sequence", str(position.transition_sequence))
    pnl_one, pnl_two, pnl_three = st.columns(3)
    pnl_one.metric("Realized P&L", _value(position.realized_net_pnl))
    pnl_two.metric("Unrealized P&L", _value(position.unrealized_pnl))
    pnl_three.metric("Total P&L", _value(position.total_pnl))
    risk_one, risk_two, risk_three, risk_four = st.columns(4)
    risk_one.metric("Stop", _value(position.stop_loss))
    risk_two.metric("T1", _value(position.target_1))
    risk_three.metric("T2", _value(position.target_2))
    risk_four.metric("T3", _value(position.target_3))
    st.write(f"Capital requirement: {_value(position.estimated_total_capital_requirement)}")
    st.write(f"Updated: {position.updated_at.isoformat()}")
    if position.is_terminal:
        st.write(f"Terminal reason: {_value(position.terminal_reason)}")
        st.write(f"Terminal target: {_value(position.terminal_target)}")
    _render_messages(st, "Position blockers", position.blockers)
    _render_messages(st, "Position warnings", position.warnings)
    _render_messages(st, "Position reasons", position.decision_reasons)
    st.subheader("Recent PAPER fills")
    if not position.fills:
        st.write("No persisted fills available.")
    for fill in position.fills:
        st.write(
            f"{fill.filled_at.isoformat()} | {fill.fill_type} | {fill.fill_reason} | "
            f"{_value(fill.target_name)} | {fill.side} | lots {fill.filled_lot_count} | "
            f"quantity {fill.filled_quantity} | price {fill.fill_price} | "
            f"cost {fill.estimated_trading_cost} | cash {fill.net_cash_effect}"
        )


def _position_reference_only(view: DashboardApplicationViewV1) -> bool:
    position = view.active_paper_position
    if position is None:
        return True
    if view.blockers or position.blockers:
        return True
    if "CLOSED" in view.market_session_state.upper() or "OUT_OF_SESSION" in view.market_session_state.upper():
        return True
    return any(
        item is not None and item.freshness_status.upper() == "STALE"
        for item in (view.nifty_market, view.sensex_market, view.runtime_operations)
    )


def _display_status(view: DashboardApplicationViewV1) -> tuple[str, bool]:
    state = view.market_session_state.upper()
    plan = view.primary_trade_plan
    opportunity = view.primary_opportunity
    blockers = (
        view.blockers
        + (plan.blockers if plan is not None else ())
        + (opportunity.blockers if opportunity is not None else ())
    )
    stale = any(
        item is not None and item.freshness_status.upper() == "STALE"
        for item in (view.nifty_market, view.sensex_market, view.runtime_operations)
    )
    if "CLOSED" in state or "OUT_OF_SESSION" in state:
        return "MARKET CLOSED", False
    if blockers:
        return "BLOCKED", False
    if stale:
        return "STALE", False
    if plan is not None:
        status = plan.plan_status.upper()
        if status != "READY":
            return status, False
        if _is_trade_ready_evidence(view):
            return "TRADE READY", True
        return "DATA UNAVAILABLE", False
    if opportunity is not None:
        return opportunity.opportunity_status.upper(), False
    return "DATA UNAVAILABLE", False


def _is_trade_ready_evidence(view: DashboardApplicationViewV1) -> bool:
    """Fail closed unless the already-published recommendation is coherent."""
    plan = view.primary_trade_plan
    opportunity = view.primary_opportunity
    selected = view.selected_market
    if (
        plan is None
        or opportunity is None
        or selected not in {"NIFTY", "SENSEX"}
        or "OPEN" not in view.market_session_state.upper()
        or plan.plan_status.upper() != "READY"
        or opportunity.opportunity_status.upper() != "READY"
        or plan.market.upper() != selected
    ):
        return False
    selected_market = (
        view.nifty_market if selected == "NIFTY" else view.sensex_market
    )
    if selected_market is None or selected_market.blockers:
        return False
    market_status = selected_market.market_status.upper()
    data_status = selected_market.data_status.upper()
    if (
        selected_market.freshness_status.upper() == "STALE"
        or "CLOSED" in market_status
        or market_status in {"BLOCKED", "UNAVAILABLE", "NO_DATA"}
        or data_status in {"BLOCKED", "UNAVAILABLE", "NO_DATA"}
    ):
        return False
    action = opportunity.action.upper()
    option_type = (opportunity.option_type or "").upper()
    if action in {"WAIT", "NO_TRADE"} or option_type in {"WAIT", "NO_TRADE"}:
        return False
    return action in {"CALL", "PUT"} or option_type in {"CALL", "PUT"}


def _render_recommendation_details(st: Any, view: DashboardApplicationViewV1) -> None:
    plan = view.primary_trade_plan
    opportunity = view.primary_opportunity
    left, middle, right = st.columns(3)
    left.write(f"Contract: {_value(_first(getattr(plan, 'selected_option_symbol', None), getattr(opportunity, 'trading_symbol', None)))}")
    left.write(f"Strike: {_value(_first(getattr(plan, 'strike', None), getattr(opportunity, 'strike', None)))}")
    left.write(f"Expiry: {_value(_first(getattr(plan, 'expiry', None), getattr(opportunity, 'expiry', None)))}")
    left.write(f"Quantity: {_value(getattr(plan, 'quantity', None))}")
    middle.write(f"Entry lower: {_value(getattr(plan, 'entry_zone_lower', None))}")
    middle.write(f"Entry upper: {_value(getattr(plan, 'entry_zone_upper', None))}")
    middle.write(f"Reference premium: {_value(_first(getattr(plan, 'entry_reference_price', None), getattr(opportunity, 'reference_option_price', None)))}")
    middle.write(f"Maximum chase: {_value(getattr(plan, 'maximum_chase_price', None))}")
    middle.write(f"Stop loss: {_value(getattr(plan, 'stop_loss_price', None))}")
    right.write(f"Required PAPER capital: {_value(getattr(plan, 'required_capital', None))}")
    right.write(f"Risk: {_value(_first(getattr(plan, 'risk_amount', None), getattr(plan, 'maximum_permissible_loss', None)))}")
    right.write(f"Estimated charges: {_value(getattr(plan, 'estimated_total_charges', None))}")
    for target in getattr(plan, "targets", ()):
        right.write(f"{target.target_name}: {_value(target.target_price)}")
    _render_messages(st, "Invalidation rules", getattr(plan, "invalidation_rules", ()))
    _render_messages(st, "Warnings/reasons", (getattr(opportunity, "supporting_evidence", ()) + getattr(opportunity, "contradictions", ()) + getattr(plan, "warnings", ()) + getattr(plan, "decision_reasons", ())))


def _render_market_card(column: Any, name: str, market: Any, selected: str | None) -> None:
    column.subheader(name)
    if market is None:
        column.write("Status: Unavailable")
        return
    column.write(f"Market status: {market.market_status}")
    column.write(f"Data status: {market.data_status}")
    column.write(f"Freshness: {market.freshness_status}")
    column.write("Selection: SELECTED" if selected == name else "Selection: REJECTED")
    _render_messages(column, "Warnings", market.warnings)
    _render_messages(column, "Blockers", market.blockers)


def _render_messages(target: Any, label: str, messages: tuple[str, ...]) -> None:
    target.write(f"{label}:")
    if not messages:
        target.write("—")
        return
    for item in messages:
        target.write(f"- {item}")


def _first(*values: object) -> object | None:
    return next((value for value in values if value is not None), None)


def _value(value: object | None) -> str:
    return "Unavailable" if value is None else str(value)
