"""Read-only dashboard rendering for Task 9 decision observability."""

from __future__ import annotations

from services.dashboard_read_models.task9_decision_observability_view_v1 import (
    Task9DecisionObservabilityDashboardViewV1,
)


def _stage(
    value: bool,
) -> str:
    return "REACHED" if value else "NOT REACHED"


def render_task9_decision_observability(
    *,
    st,
    view: Task9DecisionObservabilityDashboardViewV1 | None,
) -> None:
    st.subheader("Decision History")

    if view is None:
        st.info(
            "Certified typed decision observability is not "
            "available for the selected/current prediction yet. "
            "The dashboard does not query the legacy SQLite "
            "decision log."
        )
        return

    st.caption(
        "READ-ONLY TASK 9 DECISION OBSERVABILITY · "
        "PAPER CERTIFICATION AUTHORITY UNCHANGED"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Market",
        view.market,
    )
    c2.metric(
        "Action",
        view.action,
    )
    c3.metric(
        "Direction",
        view.direction,
    )
    c4.metric(
        "Eligibility",
        view.eligibility,
    )

    st.write(
        f"First causal blocker: {view.first_blocker}"
    )

    st.write(
        f"Concurrent blockers: {view.blocker_count}"
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Confidence / Required",
        view.confidence_text,
    )

    c2.metric(
        "Directional families / Required",
        view.family_text,
    )

    st.write("Decision funnel")

    stage_rows = (
        (
            "Candidate",
            view.candidate_reached,
        ),
        (
            "Option ranking",
            view.ranking_reached,
        ),
        (
            "Trade planning",
            view.planning_reached,
        ),
        (
            "Capital authority",
            view.capital_reached,
        ),
        (
            "PAPER entry",
            view.paper_entry_reached,
        ),
    )

    for name, reached in stage_rows:
        st.write(
            f"{name}: {_stage(reached)}"
        )

    st.write(
        f"Capital status: {view.capital_status}"
    )

    if view.blockers:
        st.write("Blockers")

        for blocker in view.blockers:
            st.warning(blocker)

    if view.decision_reasons:
        st.write("Decision reasons")

        for reason in view.decision_reasons:
            st.write(reason)

    if view.provider_summary:
        st.write("Provider participation")

        for provider in view.provider_summary:
            st.write(provider)


__all__ = (
    "render_task9_decision_observability",
)
