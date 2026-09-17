"""Compact display-only health strip over published dashboard read models."""
from __future__ import annotations

from typing import Any

from dashboard.dashboard_status_components import DashboardPublicationStatusViewV1
from services.dashboard_read_models import DashboardApplicationViewV1


def render_data_health_strip(*, st: Any, view: DashboardApplicationViewV1, publication_status: DashboardPublicationStatusViewV1) -> None:
    if type(view) is not DashboardApplicationViewV1 or type(publication_status) is not DashboardPublicationStatusViewV1:
        raise TypeError("published health view")
    st.subheader("DATA HEALTH / FRESHNESS")
    overall = _overall(view, publication_status)
    st.write(f"Overall display state: {overall} | Session: {view.market_session_state} | Publication: {publication_status.publication_status or 'Unavailable'} / {publication_status.freshness_status or 'Unavailable'}")
    nifty, sensex, selected = st.columns(3)
    _market(nifty, "NIFTY", view.nifty_market, view.selected_market)
    _market(sensex, "SENSEX", view.sensex_market, view.selected_market)
    selected.write(f"Selected-market health: {view.selected_market or 'Unavailable'}")
    runtime = view.runtime_operations
    if runtime is None:
        st.write("Runtime: Unavailable | Option quote freshness: Unavailable | Instrument master health: Unavailable")
    else:
        st.write(f"Runtime: {runtime.runtime_status} / {runtime.freshness_status} | Last successful cycle: {_time(runtime.last_successful_cycle_at)} | Last failed attempt: {_time(runtime.last_failed_attempt_at)}")
        if runtime.last_failed_attempt_error is not None: st.write(f"Runtime last failure: {runtime.last_failed_attempt_error}")
        for item in runtime.components: st.write(f"Component {item.component}: {item.status} | {item.detail or '—'}")
        for warning in runtime.warnings: st.warning(f"Runtime warning: {warning}")
        st.write("Option quote freshness: Unavailable | Instrument master health: Unavailable")
    blocker = view.external_provider_blocker
    if blocker is not None:
        st.warning(
            "Provider blocker: "
            f"{blocker['blocker_code']} | {blocker['status']} | "
            f"{blocker['endpoint']} | reason: "
            f"{blocker.get('last_failure_reason') or 'Unavailable'} | "
            f"last probe: {blocker['last_probe_result'] or 'Unavailable'} | "
            f"consecutive rate limits: "
            f"{blocker.get('consecutive_rate_limit_count', 'Unavailable')} | "
            f"occurrences: {blocker['occurrence_count']} | next probe: "
            f"{_time(blocker['next_probe_not_before'])}"
        )
    for item in view.blockers: st.warning(f"Blocker: {item}")
    for item in view.warnings: st.warning(f"Warning: {item}")


def _market(target: Any, name: str, market: Any, selected: str | None) -> None:
    if market is None:
        target.write(f"{name}: Unavailable")
        return
    target.write(f"{name}: {market.data_status} / {market.freshness_status} | Session: {market.market_status} | Observed: {market.observed_at.isoformat()}")
    if selected == name: target.write("SELECTED MARKET")
    for item in market.blockers: target.write(f"Blocker: {item}")
    for item in market.warnings: target.write(f"Warning: {item}")


def _overall(view: DashboardApplicationViewV1, status: DashboardPublicationStatusViewV1) -> str:
    selected = view.nifty_market if view.selected_market == "NIFTY" else view.sensex_market if view.selected_market == "SENSEX" else None
    if view.blockers or (selected is not None and selected.blockers): return "BLOCKED"
    if "CLOSED" in view.market_session_state.upper() or "OUT_OF_SESSION" in view.market_session_state.upper(): return "REFERENCE ONLY"
    if view.runtime_operations is not None and view.runtime_operations.runtime_status.upper() in {"FAILED", "UNAVAILABLE", "OFFLINE"}: return "REFERENCE ONLY"
    if (status.freshness_status or "").upper() == "STALE" or (view.runtime_operations is not None and view.runtime_operations.freshness_status.upper() == "STALE"): return "REFERENCE ONLY"
    if selected is None or selected.data_status.upper() in {"UNAVAILABLE", "NO_DATA"}: return "REFERENCE ONLY"
    return "ACTIONABLE DISPLAY STATE"


def _time(value: object) -> str:
    if value is None:
        return "Unavailable"
    return value if isinstance(value, str) else value.isoformat()
