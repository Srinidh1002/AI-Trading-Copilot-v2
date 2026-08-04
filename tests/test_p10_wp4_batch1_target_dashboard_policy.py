from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP4_LEGACY_DASHBOARD_AUTHORITY_AUDIT.md"
DESIGN = ROOT / "docs" / "P10_WP4_READ_MODEL_DESIGN.md"

def test_audit_defines_pure_renderer_target():
    value = AUDIT.read_text(encoding="utf-8")
    assert "pure renderer" in value
    assert "never initiates authoritative work" in value
    assert "PAPER safety" in value

def test_design_defines_all_replacement_view_families():
    value = DESIGN.read_text(encoding="utf-8")
    for token in (
        "DashboardMarketOverviewViewV1",
        "DashboardOptionIntelligenceViewV1",
        "DashboardValidationSummaryViewV1",
        "DashboardDecisionHistoryViewV1",
        "DashboardRuntimeOperationsViewV1",
    ):
        assert token in value

def test_design_freezes_forbidden_dashboard_operations():
    value = DESIGN.read_text(encoding="utf-8")
    for token in (
        "sqlite3", "get_market_snapshot", "DashboardAnalysisService",
        "get_trade_statistics", "performance_monitor", "history_cache",
        "health_check",
    ):
        assert token in value
