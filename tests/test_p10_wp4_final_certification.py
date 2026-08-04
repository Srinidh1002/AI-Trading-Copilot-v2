import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"
APP = ROOT / "app.py"
CERT = ROOT / "docs" / "P10_WP4_CERTIFICATION.md"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_active_dashboard_has_no_legacy_authority_imports():
    forbidden = (
        "sqlite3",
        "pandas",
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.performance",
        "services.performance_engine",
        "services.health",
        "services.refresh",
        "database",
    )

    for module in imported_modules(DASHBOARD):
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_active_dashboard_has_no_legacy_authority_calls_or_paths():
    source = DASHBOARD.read_text(encoding="utf-8")

    for token in (
        "get_market_snapshot",
        "DashboardAnalysisService",
        "dashboard_trade_presentation",
        "get_trade_statistics",
        "performance_monitor",
        "performance_engine",
        "history_cache",
        "safe_execute",
        "health_check",
        "database/ai_trading.db",
        "sqlite3.connect",
        "FROM decision_log",
        "@st.fragment",
        "run_every",
    ):
        assert token not in source, token


def test_active_dashboard_reads_and_renders_only_certified_boundaries():
    source = DASHBOARD.read_text(encoding="utf-8")

    required = (
        "synchronize_registered_dashboard_publication(",
        "get_plan_position_views(st.session_state)",
        "get_operational_views(st.session_state)",
        "render_plan_and_position_dashboard(",
        "render_operational_dashboard(",
    )
    for token in required:
        assert token in source


def test_unavailable_sections_do_not_reintroduce_fallback_authority():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "Certified market-overview data is not available yet" in source
    assert (
        "Certified portfolio validation statistics are not available yet"
        in source
    )
    assert "Certified typed decision history is not available yet" in source


def test_app_is_ui_bootstrap_only():
    modules = imported_modules(APP)

    assert modules == {"streamlit", "dashboard.dashboard_v2"}
    source = APP.read_text(encoding="utf-8")
    assert "services.market" not in source
    assert "live_multi_timeframe_data" not in source


def test_certification_freezes_paper_only_safety():
    source = CERT.read_text(encoding="utf-8")

    assert "PAPER-only" in source
    assert "LIVE-ineligible" in source
    assert "broker-inactive" in source
    assert "Streamlit rerun never initiates authoritative work" in source
