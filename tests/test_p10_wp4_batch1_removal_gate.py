from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


FORBIDDEN_FINAL_TOKENS = (
    "import sqlite3",
    "import pandas",
    "get_market_snapshot",
    "DashboardAnalysisService",
    "dashboard_trade_presentation",
    "get_trade_statistics",
    "performance_monitor",
    "history_cache",
    "safe_execute",
    "health_check",
    "database/ai_trading.db",
    "sqlite3.connect",
    "FROM decision_log",
)


def test_final_removal_gate_is_satisfied():
    value = DASHBOARD.read_text(encoding="utf-8")

    present = tuple(
        token for token in FORBIDDEN_FINAL_TOKENS if token in value
    )
    assert present == ()
