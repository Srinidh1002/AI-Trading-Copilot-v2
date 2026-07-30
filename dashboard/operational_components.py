from __future__ import annotations

from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


def _number(value: float | None, *, digits: int = 2) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:,.{digits}f}"


def _timestamp(value) -> str:
    if value is None:
        return "Unavailable"
    return value.isoformat()


def render_option_intelligence(
    st,
    view: DashboardOptionIntelligenceViewV1 | None,
) -> None:
    st.subheader("Option Intelligence")

    if view is None:
        st.info(
            "Certified option-intelligence data is not available yet."
        )
        return

    if type(view) is not DashboardOptionIntelligenceViewV1:
        st.error("Option-intelligence state is invalid.")
        return

    if view.blockers:
        st.warning("Blocked: " + " | ".join(view.blockers))
    if view.warnings:
        st.caption("Warnings: " + " | ".join(view.warnings))

    columns = st.columns(4)
    columns[0].metric("Status", view.status)
    columns[1].metric("Bias", view.directional_bias or "Unavailable")
    columns[2].metric("Confidence", _number(view.confidence))
    columns[3].metric("PCR", _number(view.pcr))

    levels = st.columns(3)
    levels[0].metric("Support", _number(view.support))
    levels[1].metric("Resistance", _number(view.resistance))
    levels[2].metric("Max Pain", _number(view.max_pain))

    with st.expander("Additional option evidence"):
        st.write(
            {
                "Flow": view.flow or "Unavailable",
                "Call OI": _number(view.call_open_interest),
                "Put OI": _number(view.put_open_interest),
                "ATM Delta": _number(view.atm_delta),
                "ATM Gamma": _number(view.atm_gamma),
                "ATM Theta": _number(view.atm_theta),
                "ATM Vega": _number(view.atm_vega),
                "Greeks summary": (
                    view.aggregate_greeks_summary or "Unavailable"
                ),
                "Source updated at": _timestamp(
                    view.source_updated_at
                ),
            }
        )


def render_runtime_operations(
    st,
    view: DashboardRuntimeOperationsViewV1 | None,
) -> None:
    st.subheader("Runtime Operations")

    if view is None:
        st.info("Certified runtime observations are not available yet.")
        return

    if type(view) is not DashboardRuntimeOperationsViewV1:
        st.error("Runtime-operations state is invalid.")
        return

    if view.warnings:
        st.caption("Warnings: " + " | ".join(view.warnings))

    columns = st.columns(4)
    columns[0].metric("Runtime", view.runtime_status)
    columns[1].metric("Freshness", view.freshness_status)
    columns[2].metric(
        "Cycle duration",
        (
            f"{view.market_cycle_duration_seconds:.3f}s"
            if view.market_cycle_duration_seconds is not None
            else "Unavailable"
        ),
    )
    columns[3].metric(
        "Decision duration",
        (
            f"{view.decision_cycle_duration_seconds:.3f}s"
            if view.decision_cycle_duration_seconds is not None
            else "Unavailable"
        ),
    )

    st.caption(
        "Last successful cycle: "
        + _timestamp(view.last_successful_cycle_at)
    )

    if view.last_failed_attempt_at is not None:
        st.warning(
            "Last failed attempt: "
            + _timestamp(view.last_failed_attempt_at)
            + (
                f" — {view.last_failed_attempt_error}"
                if view.last_failed_attempt_error
                else ""
            )
        )

    if not view.components:
        st.info("No certified component observations are available.")
        return

    rows = [
        {
            "Component": item.component,
            "Status": item.status,
            "Detail": item.detail or "",
        }
        for item in view.components
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_operational_dashboard(
    st,
    *,
    option_intelligence: (
        DashboardOptionIntelligenceViewV1 | None
    ),
    runtime_operations: DashboardRuntimeOperationsViewV1 | None,
) -> None:
    render_option_intelligence(st, option_intelligence)
    st.divider()
    render_runtime_operations(st, runtime_operations)
