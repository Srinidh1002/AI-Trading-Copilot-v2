"""Read-only Streamlit renderer for the operator application view model."""
from __future__ import annotations

from typing import Any

from services.contracts.operator_application_view_model_v1 import (
    OperatorApplicationViewModelV1,
)


def render_operator_dashboard(*, st: Any, view_model: OperatorApplicationViewModelV1) -> None:
    if type(view_model) is not OperatorApplicationViewModelV1:
        raise TypeError("view_model")
    if st is None:
        raise TypeError("st")

    st.title(view_model.title)
    st.caption(view_model.subtitle)
    st.info(view_model.read_only_notice)

    selected_col, losing_col = st.columns(2)
    selected_col.success(view_model.selected_market_banner)
    losing_col.warning(view_model.losing_market_banner)

    st.subheader("Market Comparison")
    nifty_col, sensex_col = st.columns(2)
    _render_market_card(nifty_col, view_model.nifty_card)
    _render_market_card(sensex_col, view_model.sensex_card)

    st.subheader("Recommendation")
    recommendation = view_model.recommendation_card
    action_col, confidence_col = st.columns(2)
    action_col.metric("Action", _after_colon(recommendation.action_label))
    confidence_col.metric("Confidence", _after_colon(recommendation.confidence_label))
    st.write(recommendation.selected_market_label)
    st.write(recommendation.contract_label)
    geometry_col_1, geometry_col_2, geometry_col_3 = st.columns(3)
    geometry_col_1.write(recommendation.entry_label)
    geometry_col_2.write(recommendation.stop_label)
    geometry_col_3.write(recommendation.targets_label)
    _render_messages(st, "Recommendation reasons", recommendation.explanation)

    st.subheader("Capital and Risk")
    capital = view_model.capital_card
    capital_col_1, capital_col_2, capital_col_3 = st.columns(3)
    capital_col_1.write(capital.supplied_capital_label)
    capital_col_1.write(capital.usable_capital_label)
    capital_col_2.write(capital.position_size_label)
    capital_col_2.write(capital.capital_required_label)
    capital_col_3.write(capital.maximum_loss_label)
    capital_col_3.write(capital.daily_risk_used_label)

    st.subheader("Active Trade")
    active = view_model.active_trade_card
    active_col_1, active_col_2, active_col_3 = st.columns(3)
    active_col_1.write(active.status_label)
    active_col_1.write(active.contract_label)
    active_col_2.write(active.premium_label)
    active_col_2.write(active.pnl_label)
    active_col_3.write(active.target_status_label)
    active_col_3.write(active.stop_status_label)
    st.write(active.instruction_label)
    if active.confidence_warning_label.endswith("DETERIORATING"):
        st.warning(active.confidence_warning_label)
    else:
        st.success(active.confidence_warning_label)

    st.subheader("System Health")
    health = view_model.health_card
    health_col_1, health_col_2, health_col_3 = st.columns(3)
    health_col_1.write(health.status_label)
    health_col_1.write(health.data_freshness_label)
    health_col_1.write(health.data_connection_label)
    health_col_2.write(health.broker_connection_label)
    health_col_2.write(health.mode_label)
    health_col_2.write(health.broker_submission_label)
    health_col_3.write(health.emergency_halt_label)
    health_col_3.write(health.runtime_label)
    health_col_3.write(health.journal_label)
    _render_messages(st, "System warnings", health.warnings)

    st.caption(f"Snapshot generated: {view_model.generated_at.isoformat()}")


def _render_market_card(column: Any, card: Any) -> None:
    column.subheader(f"{card.title} · {card.exchange}")
    column.metric("Score", _after_colon(card.score_label))
    column.metric("Confidence", _after_colon(card.confidence_label))
    column.write(card.direction_label)
    column.write(card.eligibility_label)
    column.write(card.freshness_label)
    _render_messages(column, "Reasons", card.reasons)
    _render_messages(column, "Rejection reasons", card.rejection_reasons)


def _render_messages(target: Any, label: str, messages: tuple[str, ...]) -> None:
    target.write(f"{label}:")
    if not messages:
        target.write("None")
        return
    for message in messages:
        target.write(f"- {message}")


def _after_colon(value: str) -> str:
    return value.split(":", 1)[1].strip()
