from __future__ import annotations

from typing import Any

from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanViewV1,
)


def _display(value: object, *, digits: int = 2) -> object:
    if value is None:
        return "—"
    if type(value) is float:
        return round(value, digits)
    return value


def _percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"₹{value:,.2f}"


def _render_diagnostics(
    st: Any,
    *,
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    reasons: tuple[str, ...] = (),
    contradictions: tuple[str, ...] = (),
) -> None:
    for item in blockers:
        st.error(item)
    for item in contradictions:
        st.warning(item)
    for item in warnings:
        st.warning(item)
    for item in reasons:
        st.info(item)


def render_opportunity_card(
    st: Any,
    opportunity: DashboardOpportunityViewV1 | None,
) -> None:
    if opportunity is None:
        st.info("No certified P6 opportunity is available.")
        return
    if type(opportunity) is not DashboardOpportunityViewV1:
        raise TypeError("opportunity must be DashboardOpportunityViewV1 or None")

    st.subheader("P6 Opportunity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market", f"{opportunity.underlying_symbol} · {opportunity.exchange}")
    c2.metric("Status", opportunity.opportunity_status)
    c3.metric("Action", opportunity.action)
    c4.metric("Opportunity score", _percent(opportunity.opportunity_score))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bias", opportunity.directional_bias)
    c2.metric("Option type", opportunity.option_type or "—")
    c3.metric("Strike", _display(opportunity.strike))
    c4.metric("Reference premium", _money(opportunity.reference_option_price))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Technical", _percent(opportunity.technical_strength))
    c2.metric("Option chain", _percent(opportunity.option_chain_strength))
    c3.metric("Contract rank", _percent(opportunity.contract_ranking_score))
    c4.metric("Decision confidence", _percent(opportunity.decision_confidence))

    st.caption(
        "PAPER only · "
        f"Opportunity {opportunity.opportunity_id} · "
        f"Created {opportunity.created_at.isoformat()}"
    )
    _render_diagnostics(
        st,
        blockers=opportunity.blockers,
        warnings=opportunity.warnings,
        contradictions=opportunity.contradictions,
        reasons=opportunity.supporting_evidence,
    )


def render_trade_plan_card(
    st: Any,
    plan: DashboardTradePlanViewV1 | None,
) -> None:
    if plan is None:
        st.info("No certified P6 trade plan is available.")
        return
    if type(plan) is not DashboardTradePlanViewV1:
        raise TypeError("plan must be DashboardTradePlanViewV1 or None")

    st.subheader("P6 Three-Target Trade Plan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", plan.plan_status)
    c2.metric("Market", f"{plan.market} · {plan.exchange}")
    c3.metric("Direction", plan.direction)
    c4.metric("Plan confidence", _percent(plan.plan_confidence))

    if plan.plan_status != "READY":
        _render_diagnostics(
            st,
            blockers=plan.blockers,
            warnings=plan.warnings,
            reasons=plan.decision_reasons,
        )
        st.caption(
            f"PAPER only · Plan {plan.trade_plan_id} · "
            f"Evaluated {plan.evaluated_at.isoformat()}"
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Option", plan.selected_option_symbol or "—")
    c2.metric("Strike", _display(plan.strike))
    c3.metric("Expiry", str(plan.expiry) if plan.expiry else "—")
    c4.metric("Quantity", _display(plan.quantity))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entry lower", _money(plan.entry_zone_lower))
    c2.metric("Entry upper", _money(plan.entry_zone_upper))
    c3.metric("Reference", _money(plan.entry_reference_price))
    c4.metric("Max chase", _money(plan.maximum_chase_price))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stop loss", _money(plan.stop_loss_price))
    c2.metric("Risk", _money(plan.risk_amount))
    c3.metric("Required capital", _money(plan.required_capital))
    c4.metric("Charges", _money(plan.estimated_total_charges))

    st.markdown("#### Targets")
    columns = st.columns(3)
    for column, target in zip(columns, plan.targets):
        column.metric(target.target_name, _money(target.target_price))
        column.caption(
            " · ".join(
                (
                    f"Lots: {_display(target.lot_count)}",
                    f"Qty: {_display(target.quantity)}",
                    f"RR: {_display(target.reward_to_risk)}",
                    f"Book: {_percent(target.booking_fraction)}",
                )
            )
        )
        for warning in target.warnings:
            column.warning(warning)

    if plan.invalidation_rules:
        st.markdown("#### Invalidation rules")
        for item in plan.invalidation_rules:
            st.write(f"• {item}")

    _render_diagnostics(
        st,
        warnings=plan.warnings,
        reasons=plan.decision_reasons,
    )
    st.caption(
        f"PAPER only · Plan {plan.trade_plan_id} · "
        f"Evaluated {plan.evaluated_at.isoformat()}"
    )


def render_paper_position_card(
    st: Any,
    position: DashboardPaperPositionDetailViewV1 | None,
) -> None:
    if position is None:
        st.info("No certified P7 paper position is available.")
        return
    if type(position) is not DashboardPaperPositionDetailViewV1:
        raise TypeError(
            "position must be DashboardPaperPositionDetailViewV1 or None"
        )

    st.subheader("P7 Paper Position")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lifecycle", position.lifecycle_state)
    c2.metric("Group", position.lifecycle_display_group)
    c3.metric("Paper trade", position.paper_trade_id)
    c4.metric("Terminal", "Yes" if position.is_terminal else "No")

    if position.position_id is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Instrument", position.option_symbol or "—")
        c2.metric("Entry", _money(position.entry_price))
        c3.metric("Remaining qty", _display(position.remaining_quantity))
        c4.metric("Current premium", _money(position.current_option_price))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stop", _money(position.stop_loss))
        c2.metric("T1", _money(position.target_1))
        c3.metric("T2", _money(position.target_2))
        c4.metric("T3", _money(position.target_3))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Realized P&L", _money(position.realized_net_pnl))
        c2.metric("Unrealized P&L", _money(position.unrealized_pnl))
        c3.metric("Total P&L", _money(position.total_pnl))
        c4.metric(
            "Capital",
            _money(position.estimated_total_capital_requirement),
        )

    if position.terminal_reason:
        st.info(f"Terminal reason: {position.terminal_reason}")
    if position.terminal_target:
        st.info(f"Terminal target: {position.terminal_target}")

    if position.fills:
        st.markdown("#### Persisted fill history")
        rows = tuple(
            {
                "Time": item.filled_at.isoformat(),
                "Type": item.fill_type,
                "Reason": item.fill_reason,
                "Target": item.target_name or "—",
                "Side": item.side,
                "Lots": item.filled_lot_count,
                "Quantity": item.filled_quantity,
                "Price": item.fill_price,
                "Cost": item.estimated_trading_cost,
                "Net cash effect": item.net_cash_effect,
            }
            for item in position.fills
        )
        st.dataframe(rows, use_container_width=True, hide_index=True)

    _render_diagnostics(
        st,
        blockers=position.blockers,
        warnings=position.warnings,
        reasons=position.decision_reasons,
    )
    st.caption(
        "PAPER only · "
        f"Updated {position.updated_at.isoformat()} · "
        f"Transition {position.transition_sequence}"
    )


def render_plan_and_position_dashboard(
    st: Any,
    *,
    opportunity: DashboardOpportunityViewV1 | None,
    plan: DashboardTradePlanViewV1 | None,
    position: DashboardPaperPositionDetailViewV1 | None,
) -> None:
    st.header("Certified PAPER Plan and Position")
    render_opportunity_card(st, opportunity)
    st.divider()
    render_trade_plan_card(st, plan)
    st.divider()
    render_paper_position_card(st, position)
