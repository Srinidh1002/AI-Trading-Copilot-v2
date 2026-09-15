import streamlit as st

from config import APP_NAME, BUILD, PHASE, VERSION
from dashboard.dashboard_operational_read_model_state import (
    get_operational_views,
)
from dashboard.dashboard_publication_sync import (
    DEFAULT_TASK9_PUBLICATION_ROOT,
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY,
    get_operator_application_view_model,
    render_operator_dashboard,
    synchronize_registered_dashboard_publication,
)
from dashboard.dashboard_read_model_state import get_plan_position_views
from dashboard.dashboard_read_model_state import (
    build_task9_prepublication_application_view,
    get_application_view,
    get_r4_paper_lifecycle_view,
    get_task9_decision_observability_view,
    recover_task9_durable_authorities,
)
from dashboard.task9_active_campaign_sync import (
    synchronize_task9_active_campaign_projection,
)
from dashboard.task9_decision_observability_sync import (
    synchronize_task9_decision_observability,
)
from dashboard.dashboard_read_model_state import (
    get_r4_paper_lifecycle_view,
)
from dashboard.operational_components import (
    render_operational_dashboard,
)
from dashboard.plan_position_components import render_plan_and_position_dashboard
from dashboard.plan_position_components import (
    render_r4_paper_lifecycle_dashboard,
)
from dashboard.trade_now_components import render_trade_now_dashboard
from dashboard.dashboard_status_components import (
    get_dashboard_publication_status_view,
    render_dashboard_status,
)
from dashboard.trades_pnl_components import render_trades_pnl_center
from dashboard.task9_certification_components import render_task9_certification_center
from dashboard.recommendation_history_components import render_recommendation_history
from dashboard.data_health_components import render_data_health_strip
from dashboard.decision_observability_components import (
    render_task9_decision_observability,
)
from dashboard.manual_live_planner_components import render_manual_live_planner
from dashboard.dashboard_navigation import render_dashboard_navigation
from dashboard.markets_components import render_markets_comparison


_OPERATOR_VIEW_MODEL_KEY = (
    OPERATOR_APPLICATION_VIEW_MODEL_STATE_KEY
)


def _render_unavailable_sections(
    decision_observability_view=None,
) -> None:
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

    render_task9_decision_observability(
        st=st,
        view=decision_observability_view,
    )


def _render_r4_lifecycle_section(view) -> None:
    if view is None:
        st.subheader("PAPER Portfolio Lifecycle")
        st.info(
            "No certified persisted R4 lifecycle view "
            "has been published."
        )
        return

    render_r4_paper_lifecycle_dashboard(
        st=st,
        view=view,
    )


def home() -> None:
    synchronize_registered_dashboard_publication(
        st.session_state
    )

    synchronize_task9_active_campaign_projection(
        st.session_state,
        persistence_root=(
            DEFAULT_TASK9_PUBLICATION_ROOT
        ),
    )

    synchronize_task9_decision_observability(
        st.session_state,
        registry_root=(
            DEFAULT_TASK9_PUBLICATION_ROOT
        ),
    )

    operator_view_model = get_operator_application_view_model(
        st.session_state
    )
    application_view = get_application_view(st.session_state)

    if application_view is None and operator_view_model is None:
        application_view = build_task9_prepublication_application_view()
        st.session_state["dashboard_application_view_v1"] = application_view

    if application_view is None and operator_view_model is not None:
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

    if application_view is not None:
        application_view = recover_task9_durable_authorities(
            application_view,
            persistence_root=DEFAULT_TASK9_PUBLICATION_ROOT,
        )
        st.title("AI TRADING COPILOT")
        st.caption("PAPER CERTIFICATION MODE · PAPER ONLY · BROKER ORDER SUBMISSION DISABLED")
        page = render_dashboard_navigation(st)
        status = get_dashboard_publication_status_view(st.session_state)
        if page == "🎯 Trade Now":
            render_trade_now_dashboard(st=st, view=application_view)
            if operator_view_model is not None:
                st.divider(); render_operator_dashboard(st=st, view_model=operator_view_model)
        elif page == "📊 Markets":
            render_markets_comparison(st=st, view=application_view)
            st.divider()
            render_recommendation_history(st=st, view=application_view)
        elif page == "💼 Trades & P&L":
            render_trades_pnl_center(st=st, view=application_view)
        elif page == "🧪 Certification":
            render_task9_certification_center(st=st, view=application_view)
        elif page == "🧮 Manual Planner":
            render_manual_live_planner(st=st, view=application_view)
        else:
            render_dashboard_status(st=st, status=status, application_view=application_view)
            render_data_health_strip(st=st, view=application_view, publication_status=status)
        st.divider()
        st.caption(f"{APP_NAME} | Version {VERSION} | {PHASE} | Build {BUILD}")
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

    r4_lifecycle_view = get_r4_paper_lifecycle_view(
        st.session_state
    )

    decision_observability_view = (
        get_task9_decision_observability_view(
            st.session_state
        )
    )

    st.title("🤖 AI Trading Copilot V2")
    st.caption("Unified application view is unavailable; certified fallback read models only")
    st.divider()

    render_plan_and_position_dashboard(
        st,
        opportunity=opportunity_view,
        plan=trade_plan_view,
        position=paper_position_view,
    )

    st.divider()

    _render_r4_lifecycle_section(r4_lifecycle_view)

    st.divider()

    render_operational_dashboard(
        st,
        option_intelligence=option_intelligence_view,
        runtime_operations=runtime_operations_view,
    )

    st.divider()

    _render_unavailable_sections(
        decision_observability_view
    )

    st.divider()
    st.caption(
        f"{APP_NAME} | Version {VERSION} | "
        f"{PHASE} | Build {BUILD}"
    )
