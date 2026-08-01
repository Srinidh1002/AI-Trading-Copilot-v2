import streamlit as st

from config import APP_NAME, BUILD, PHASE, VERSION
from dashboard.dashboard_operational_read_model_state import (
    get_operational_views,
)
from dashboard.dashboard_publication_sync import (
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY,
    get_operator_application_view_model,
    render_operator_dashboard,
    synchronize_registered_dashboard_publication,
)
from dashboard.dashboard_read_model_state import get_plan_position_views
from dashboard.operational_components import (
    render_operational_dashboard,
)
from dashboard.plan_position_components import render_plan_and_position_dashboard


_OPERATOR_VIEW_MODEL_KEY = (
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY
)


def _render_unavailable_sections() -> None:
    st.subheader("Market Overview")
    st.info(
        "Certified market-overview data is not available yet. "
        "The dashboard will not fetch or calculate it independently."
    )

    st.divider()

    st.subheader("Validation")
    st.info(
        "Certified portfolio validation statistics are not available yet."
    )

    st.divider()

    st.subheader("Decision History")
    st.info(
        "Certified typed decision history is not available yet. "
        "The dashboard does not query the legacy SQLite decision log."
    )


def home() -> None:
    synchronize_registered_dashboard_publication(
        st.session_state
    )

    operator_view_model = (
        get_operator_application_view_model(
            st.session_state
        )
    )
    if operator_view_model is not None:
        render_operator_dashboard(
            st=st,
            view_model=operator_view_model,
        )
        st.divider()
        st.caption(
            f"{APP_NAME} | Version {VERSION} | "
            f"{PHASE} | Build {BUILD}"
        )
        return

    (
        opportunity_view,
        trade_plan_view,
        paper_position_view,
    ) = get_plan_position_views(st.session_state)

    (
        option_intelligence_view,
        runtime_operations_view,
    ) = get_operational_views(st.session_state)

    st.title("🤖 AI Trading Copilot V2")
    st.caption(
        "Certified PAPER dashboard — immutable published read models only"
    )
    st.divider()

    render_plan_and_position_dashboard(
        st,
        opportunity=opportunity_view,
        plan=trade_plan_view,
        position=paper_position_view,
    )

    st.divider()

    render_operational_dashboard(
        st,
        option_intelligence=option_intelligence_view,
        runtime_operations=runtime_operations_view,
    )

    st.divider()

    _render_unavailable_sections()

    st.divider()
    st.caption(
        f"{APP_NAME} | Version {VERSION} | "
        f"{PHASE} | Build {BUILD}"
    )
