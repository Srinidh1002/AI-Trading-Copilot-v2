"""Read-only two-market comparison from published application state."""
from __future__ import annotations

from typing import Any

from services.dashboard_read_models import DashboardApplicationViewV1


def render_markets_comparison(*, st: Any, view: DashboardApplicationViewV1) -> None:
    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")
    st.subheader("PUBLISHED NIFTY / SENSEX MARKET EVIDENCE")
    nifty, sensex = st.columns(2)
    _market(nifty, "NIFTY", view.nifty_market, view.selected_market)
    _market(sensex, "SENSEX", view.sensex_market, view.selected_market)
    st.write(f"Selected market: {view.selected_market or 'Unavailable'}")
    _messages(st, "Why selected", view.selected_market_rationale)
    _messages(st, "Why not the other market", view.rejected_market_rationale)


def _market(target: Any, name: str, market: Any, selected: str | None) -> None:
    target.subheader(name)
    if market is None:
        target.write("Published market evidence: Unavailable")
        return
    target.write(f"Market status: {market.market_status} | Data status: {market.data_status} | Freshness: {market.freshness_status}")
    target.write(f"Observed: {market.observed_at.isoformat()} | Selection: {'SELECTED' if selected == name else 'NOT SELECTED'}")
    _messages(target, "Blockers", market.blockers)
    _messages(target, "Warnings", market.warnings)


def _messages(target: Any, label: str, items: tuple[str, ...]) -> None:
    target.write(f"{label}:")
    if not items:
        target.write("—")
    for item in items:
        target.write(f"- {item}")
