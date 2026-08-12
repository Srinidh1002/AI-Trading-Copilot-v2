from dashboard.dashboard_navigation import (
    DASHBOARD_PAGES,
    DEFAULT_DASHBOARD_PAGE,
    NAVIGATION_STATE_KEY,
    normalize_dashboard_page,
    render_dashboard_navigation,
)
from dashboard.markets_components import render_markets_comparison
from services.dashboard_read_models import DashboardApplicationViewV1, DashboardMarketStateV1
from datetime import datetime, timezone


def test_navigation_has_exact_pages_and_safe_default():
    assert DASHBOARD_PAGES == (
        "🎯 Trade Now", "📊 Markets", "💼 Trades & P&L", "🧪 Certification", "🧮 Manual Planner", "⚙️ System Health",
    )
    assert DEFAULT_DASHBOARD_PAGE == "🎯 Trade Now"
    assert normalize_dashboard_page(None) == DEFAULT_DASHBOARD_PAGE
    assert normalize_dashboard_page("bad") == DEFAULT_DASHBOARD_PAGE
    assert NAVIGATION_STATE_KEY == "dashboard_v2_active_page"


def test_fragment_safe_navigation_preserves_existing_session_selection():
    class Sidebar:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def radio(self, label, pages, index):
            assert label == "Dashboard" and pages == DASHBOARD_PAGES
            return pages[index]
    class Fake:
        def __init__(self):
            self.sidebar = Sidebar()
            self.session_state = {NAVIGATION_STATE_KEY: "🧪 Certification"}

    st = Fake()
    assert render_dashboard_navigation(st) == "🧪 Certification"
    assert st.session_state[NAVIGATION_STATE_KEY] == "🧪 Certification"


def test_markets_comparison_keeps_both_markets_and_rationales_visible():
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    class Fake:
        def __init__(self, events=None): self.events=[] if events is None else events
        def subheader(self, v): self.events.append(("subheader", v))
        def write(self, v): self.events.append(("write", v))
        def columns(self, n): return tuple(Fake(self.events) for _ in range(n))
    market = lambda name: DashboardMarketStateV1(name, name, now, "OPEN", "PUBLISHED", "FRESH")
    view = DashboardApplicationViewV1("view", now, "OPEN", nifty_market=market("NIFTY"), sensex_market=market("SENSEX"), selected_market="NIFTY", selected_market_rationale=("NIFTY stronger.",), rejected_market_rationale=("SENSEX weaker.",))
    st=Fake(); render_markets_comparison(st=st, view=view)
    assert ("subheader", "NIFTY") in st.events and ("subheader", "SENSEX") in st.events
    assert ("write", "- NIFTY stronger.") in st.events
    assert ("write", "- SENSEX weaker.") in st.events
