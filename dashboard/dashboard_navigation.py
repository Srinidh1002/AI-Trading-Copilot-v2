"""UI-only navigation for the certified dashboard shell."""
from __future__ import annotations

from typing import Any

DASHBOARD_PAGES = ("🎯 Trade Now", "📊 Markets", "💼 Trades & P&L", "🧪 Certification", "🧮 Manual Planner", "⚙️ System Health")
DEFAULT_DASHBOARD_PAGE = DASHBOARD_PAGES[0]
NAVIGATION_STATE_KEY = "dashboard_v2_active_page"

def normalize_dashboard_page(value: object) -> str:
    return value if type(value) is str and value in DASHBOARD_PAGES else DEFAULT_DASHBOARD_PAGE

def render_dashboard_navigation(st: Any) -> str:
    state = st.session_state
    selected = normalize_dashboard_page(state.get(NAVIGATION_STATE_KEY))
    sidebar = getattr(st, "sidebar", None)
    radio = getattr(sidebar, "radio", None)
    if callable(radio):
        # Streamlit fragments require sidebar elements to be rendered through
        # its context manager.  Headless dashboard tests use a lightweight
        # sidebar object, so retain the direct UI-only fallback there.
        if callable(getattr(sidebar, "__enter__", None)):
            with sidebar:
                selected = normalize_dashboard_page(radio("Dashboard", DASHBOARD_PAGES, index=DASHBOARD_PAGES.index(selected)))
        else:
            selected = normalize_dashboard_page(radio("Dashboard", DASHBOARD_PAGES, index=DASHBOARD_PAGES.index(selected)))
    state[NAVIGATION_STATE_KEY] = selected
    return selected
