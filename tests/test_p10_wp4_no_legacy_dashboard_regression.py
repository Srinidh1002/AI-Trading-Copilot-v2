from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


FORBIDDEN = (
    "sqlite3",
    "pandas",
    "get_market_snapshot",
    "DashboardAnalysisService",
    "dashboard_trade_presentation",
    "get_trade_statistics",
    "performance_monitor",
    "performance_engine",
    "history_cache",
    "safe_execute",
    "health_check",
    "paper_trade_manager",
    "database/ai_trading.db",
    "decision_log",
    "market_snapshot",
)


def test_legacy_dashboard_authority_cannot_return():
    source = DASHBOARD.read_text(encoding="utf-8")

    present = tuple(token for token in FORBIDDEN if token in source)
    assert present == ()
