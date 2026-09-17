from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


def source():
    return DASHBOARD.read_text(encoding="utf-8")


def test_active_dashboard_contains_no_legacy_authorities():
    value = source()

    forbidden = (
        "sqlite3",
        "pandas",
        "get_market_snapshot",
        "DashboardAnalysisService",
        "dashboard_trade_presentation",
        "get_trade_statistics",
        "performance_monitor",
        "history_cache",
        "safe_execute",
        "health_check",
    )
    for token in forbidden:
        assert token not in value, token


def test_active_dashboard_contains_no_database_history_query():
    value = source()

    assert "database/ai_trading.db" not in value
    assert "FROM decision_log" not in value
    assert "sqlite3.connect" not in value


def test_active_dashboard_uses_only_certified_read_model_paths():
    value = source()

    assert "synchronize_registered_dashboard_publication(" in value
    assert "get_plan_position_views(st.session_state)" in value
    assert "get_operational_views(st.session_state)" in value
    assert "render_plan_and_position_dashboard(" in value
    assert "render_operational_dashboard(" in value
