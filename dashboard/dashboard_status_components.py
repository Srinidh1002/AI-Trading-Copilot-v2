"""Typed read-only publication status and offline dashboard rendering."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from services.dashboard_read_models import DashboardApplicationViewV1


@dataclass(frozen=True, slots=True)
class DashboardPublicationStatusViewV1:
    publication_id: str | None
    publication_sequence: int | None
    publication_status: str | None
    freshness_status: str | None
    published_at: datetime | None
    source_updated_at: datetime | None
    last_attempt_status: str | None
    last_attempt_error: str | None
    failed_attempt_count: int | None


def get_dashboard_publication_status_view(
    state: Mapping[str, object],
) -> DashboardPublicationStatusViewV1:
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")
    def optional_text(key: str) -> str | None:
        value = state.get(key)
        if value is None:
            return None
        if type(value) is not str:
            raise TypeError(key)
        return value
    def optional_datetime(key: str) -> datetime | None:
        value = state.get(key)
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise TypeError(key)
        return value
    def optional_count(key: str) -> int | None:
        value = state.get(key)
        if value is None:
            return None
        if type(value) is not int or isinstance(value, bool) or value < 0:
            raise TypeError(key)
        return value
    return DashboardPublicationStatusViewV1(
        optional_text("dashboard_publication_id"),
        optional_count("dashboard_publication_sequence"),
        optional_text("dashboard_publication_status"),
        optional_text("dashboard_publication_freshness"),
        optional_datetime("dashboard_publication_published_at"),
        optional_datetime("dashboard_publication_source_updated_at"),
        optional_text("dashboard_publication_attempt_status"),
        optional_text("dashboard_publication_attempt_error"),
        optional_count("dashboard_publication_failed_attempt_count"),
    )


def render_dashboard_status(
    *, st: Any, status: DashboardPublicationStatusViewV1,
    application_view: DashboardApplicationViewV1,
) -> None:
    if type(status) is not DashboardPublicationStatusViewV1:
        raise TypeError("status")
    if type(application_view) is not DashboardApplicationViewV1:
        raise TypeError("application_view")
    closed = "CLOSED" in application_view.market_session_state.upper() or "OUT_OF_SESSION" in application_view.market_session_state.upper()
    offline = _offline(application_view, status)
    if closed:
        st.warning("MARKET CLOSED · LAST PUBLISHED STATE")
        st.info("Historical and last published PAPER state is shown for reference. No current actionable trade.")
    if offline:
        st.warning("OFFLINE / LAST GOOD STATE")
    if _stale(application_view, status):
        st.warning("STALE DATA · published state shown for reference only.")
    st.caption(
        f"Publication {status.publication_id or 'Unavailable'} · sequence {status.publication_sequence if status.publication_sequence is not None else 'Unavailable'} · "
        f"status {status.publication_status or 'Unavailable'} · freshness {status.freshness_status or 'Unavailable'}"
    )
    st.write(f"Published at: {_time(status.published_at)} | Source updated: {_time(status.source_updated_at)}")
    st.write(f"Last attempt: {status.last_attempt_status or 'Unavailable'} | Failed attempts: {status.failed_attempt_count if status.failed_attempt_count is not None else 'Unavailable'}")
    if status.last_attempt_error is not None:
        st.write(f"Last attempt error: {status.last_attempt_error}")
    if application_view.portfolio is not None:
        p = application_view.portfolio
        st.write(f"Persisted PAPER portfolio — Total P&L: {p.total_pnl} | Equity: {p.total_equity}")
    if application_view.task9_certification_progress is not None:
        progress = application_view.task9_certification_progress
        st.write(f"Task 9 progress — NIFTY {progress.nifty.completed_live_paper_trades}/{progress.nifty.target_trade_count} | SENSEX {progress.sensex.completed_live_paper_trades}/{progress.sensex.target_trade_count}")


def _offline(view: DashboardApplicationViewV1, status: DashboardPublicationStatusViewV1) -> bool:
    runtime = view.runtime_operations
    return (
        (runtime is not None and runtime.runtime_status.upper() in {"FAILED", "UNAVAILABLE", "OFFLINE"})
        or (
            status.last_attempt_status == "FAILED_ATTEMPT_PRESERVED"
            and status.last_attempt_error is not None
        )
    )


def _stale(view: DashboardApplicationViewV1, status: DashboardPublicationStatusViewV1) -> bool:
    runtime = view.runtime_operations
    return (
        (status.freshness_status or "").upper() == "STALE"
        or (runtime is not None and runtime.freshness_status.upper() == "STALE")
    )


def _time(value: datetime | None) -> str:
    return "Unavailable" if value is None else value.isoformat()
