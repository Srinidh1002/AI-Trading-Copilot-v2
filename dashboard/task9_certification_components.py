"""Read-only Task 9 certification display over published progress only."""
from __future__ import annotations

from typing import Any, Mapping

from services.dashboard_read_models import DashboardApplicationViewV1


def render_task9_certification_center(*, st: Any, view: DashboardApplicationViewV1) -> None:
    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")
    st.subheader("TASK 9 CERTIFICATION CENTER")
    progress = view.task9_certification_progress
    if progress is None:
        st.info("Task 9 certification progress has not been published.")
        _render_external_provider_evidence(st, view.external_provider_blocker)
        return
    st.caption("PAPER CERTIFICATION ACTIVE · NO_TRADE is evaluated separately and never increments the live PAPER trade target.")
    nifty_col, sensex_col = st.columns(2)
    _render_market(nifty_col, progress.nifty)
    _render_market(sensex_col, progress.sensex)
    st.write(f"REPLAY EXCLUDED: {progress.replay_excluded} | DUPLICATE EXCLUDED: {progress.duplicate_excluded} | INVALID/DATA EXCLUDED: {progress.invalid_excluded} | UNRESOLVED: {progress.unresolved}")
    st.write("WAIT does not count toward the live PAPER trade target.")
    _render_external_provider_evidence(st, view.external_provider_blocker)
    if progress.certification_complete:
        st.success("CERTIFICATION COMPLETE (published authority)")
    else:
        st.info("CERTIFICATION IN PROGRESS (published authority)")


def _render_market(column: Any, progress: Any) -> None:
    column.subheader(progress.market)
    column.metric("LIVE PAPER TRADE TARGET", f"{progress.completed_live_paper_trades} / {progress.target_trade_count}")
    column.metric("Remaining", str(progress.remaining_trade_count))
    column.metric("Pending entered (not completed)", str(progress.pending_entered_trades))
    column.write(f"NO_TRADE separate — completed: {progress.no_trade_completed} | pass: {progress.no_trade_passed} | fail: {progress.no_trade_failed}")


def _render_external_provider_evidence(
    st: Any,
    blocker: Mapping[str, Any] | None,
) -> None:
    """Render published provider-operational evidence without reading authority files."""
    st.subheader("External Provider Evidence")
    if blocker is None:
        st.info("No active external-provider blocker is currently published.")
        return

    st.write(
        "Provider: "
        f"{_display(blocker.get('provider'))} | "
        f"Endpoint: {_display(blocker.get('endpoint'))} | "
        f"Blocker code: {_display(blocker.get('blocker_code'))} | "
        f"Status: {_display(blocker.get('status'))}"
    )
    st.write(
        "Last failure reason: "
        f"{_display(blocker.get('last_failure_reason'))} | "
        f"Last probe result: {_display(blocker.get('last_probe_result'))} | "
        "Consecutive rate limits: "
        f"{_display(blocker.get('consecutive_rate_limit_count'))} | "
        f"Occurrences: {_display(blocker.get('occurrence_count'))}"
    )
    st.write(
        f"Last probe at: {_display(blocker.get('last_probe_at'))} | "
        "Next probe not before: "
        f"{_display(blocker.get('next_probe_not_before'))}"
    )


def _display(value: object) -> str:
    if value is None:
        return "Unavailable"
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
