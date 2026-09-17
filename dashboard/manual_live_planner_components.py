"""Isolated, non-executable manual sizing preview from published plan data."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from services.dashboard_read_models import DashboardApplicationViewV1


@dataclass(frozen=True, slots=True)
class ManualLivePlannerPreviewV1:
    supplied_capital: float
    risk_budget: float | None
    selected_market: str | None
    option_symbol: str | None
    recommended_lot_count: int
    recommended_quantity: int
    required_capital: float
    estimated_max_loss: float | None
    published_plan_maximum_permissible_loss: float | None
    risk_basis: str
    status: str
    planning_only: bool = True
    broker_order_submission: bool = False
    live_execution_eligible: bool = False


def build_manual_live_preview(*, view: DashboardApplicationViewV1, capital: object, risk_budget: object | None = None) -> ManualLivePlannerPreviewV1:
    if type(view) is not DashboardApplicationViewV1: raise TypeError("view")
    if type(capital) not in (int, float) or isinstance(capital, bool) or not isfinite(capital) or capital <= 0: raise ValueError("capital")
    if risk_budget is not None and (type(risk_budget) not in (int, float) or isinstance(risk_budget, bool) or not isfinite(risk_budget) or risk_budget <= 0 or risk_budget > capital): raise ValueError("risk_budget")
    plan = view.primary_trade_plan
    if plan is None or plan.plan_status != "READY" or plan.lot_size is None or plan.entry_reference_price is None:
        return ManualLivePlannerPreviewV1(float(capital), None if risk_budget is None else float(risk_budget), view.selected_market, None, 0, 0, 0.0, None, None, "UNAVAILABLE", "NO_PUBLISHED_PLAN")
    if plan.lot_size <= 0 or plan.entry_reference_price <= 0:
        return ManualLivePlannerPreviewV1(float(capital), None if risk_budget is None else float(risk_budget), view.selected_market, plan.selected_option_symbol, 0, 0, 0.0, None, plan.maximum_permissible_loss, "UNAVAILABLE", "INVALID_SIZING_GEOMETRY")
    one_lot = plan.lot_size * plan.entry_reference_price
    if not isfinite(one_lot) or one_lot <= 0:
        return ManualLivePlannerPreviewV1(float(capital), None if risk_budget is None else float(risk_budget), view.selected_market, plan.selected_option_symbol, 0, 0, 0.0, None, plan.maximum_permissible_loss, "UNAVAILABLE", "INVALID_SIZING_GEOMETRY")
    capital_lots = int(float(capital) // one_lot)
    per_lot_risk = None
    if plan.risk_amount is not None and plan.risk_amount > 0 and type(plan.lot_count) is int and plan.lot_count > 0:
        per_lot_risk = plan.risk_amount / plan.lot_count
    if risk_budget is not None and per_lot_risk is None:
        return ManualLivePlannerPreviewV1(float(capital), float(risk_budget), view.selected_market, plan.selected_option_symbol, 0, 0, 0.0, None, plan.maximum_permissible_loss, "UNAVAILABLE", "RISK_GEOMETRY_UNAVAILABLE")
    lots = capital_lots if risk_budget is None else min(capital_lots, int(float(risk_budget) // per_lot_risk))
    status = "READY" if lots else ("INSUFFICIENT_RISK_BUDGET" if risk_budget is not None and capital_lots else "INSUFFICIENT_CAPITAL")
    return ManualLivePlannerPreviewV1(float(capital), None if risk_budget is None else float(risk_budget), view.selected_market, plan.selected_option_symbol, lots, lots * plan.lot_size, lots * one_lot, None if per_lot_risk is None else per_lot_risk * lots, plan.maximum_permissible_loss, "SCALED_PUBLISHED_PER_LOT_RISK" if per_lot_risk is not None else "UNAVAILABLE", status)


def render_manual_live_planner(*, st: Any, view: DashboardApplicationViewV1) -> None:
    st.subheader("MANUAL LIVE PLANNER")
    st.info("MANUAL LIVE PLANNING ONLY · ORDER SUBMISSION DISABLED · PAPER CERTIFICATION REMAINS ACTIVE")
    st.caption("Planner inputs do not affect PAPER capital, PAPER trades, Task 9 progress, or certification evidence.")
    number_input = getattr(st, "number_input", None)
    capital = number_input("Manual intended capital", min_value=0.0, value=0.0, key="manual_live_planner_capital") if callable(number_input) else 0.0
    risk = number_input("Optional risk budget", min_value=0.0, value=0.0, key="manual_live_planner_risk") if callable(number_input) else 0.0
    if capital <= 0:
        st.write("Enter a positive manual intended capital to view an isolated preview.")
        return
    preview = build_manual_live_preview(view=view, capital=capital, risk_budget=None if risk == 0 else risk)
    st.write(f"Status: {preview.status} | Market: {preview.selected_market or 'Unavailable'} | Contract: {preview.option_symbol or 'Unavailable'}")
    st.write(f"Whole lots: {preview.recommended_lot_count} | Quantity: {preview.recommended_quantity} | Estimated premium capital: {preview.required_capital} | Manual preview risk/max loss: {preview.estimated_max_loss} | Risk basis: {preview.risk_basis} | Published plan max-loss reference: {preview.published_plan_maximum_permissible_loss}")
    if "CLOSED" in view.market_session_state.upper(): st.warning("LAST PUBLISHED CONTRACT/PRICE — reference-only planning preview.")
