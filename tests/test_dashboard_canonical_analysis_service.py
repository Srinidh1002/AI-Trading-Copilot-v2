from services.dashboard.dashboard_analysis_service import (
    DashboardAnalysisMode,
    DashboardAnalysisService,
    dashboard_trade_presentation,
)


def test_legacy_mode_preserves_the_injected_legacy_analysis_result():
    legacy_trade = {"decision": "WAIT", "confidence": 0}
    service = DashboardAnalysisService(legacy_analyzer=lambda snapshot: legacy_trade)

    result = service.analyse(
        {"symbol": "NIFTY"},
        mode=DashboardAnalysisMode.LEGACY,
    )

    assert result.legacy_decision is legacy_trade
    assert dashboard_trade_presentation(result) is legacy_trade


def test_invalid_dashboard_snapshot_fails_closed_without_a_legacy_fallback():
    service = DashboardAnalysisService(legacy_analyzer=lambda snapshot: {"decision": "BUY CE"})

    result = service.analyse({}, mode=DashboardAnalysisMode.CANONICAL)

    assert dashboard_trade_presentation(result) is not None
    assert dashboard_trade_presentation(result)["decision"] == "WAIT"
    assert dashboard_trade_presentation(result)["trade_action"] == "NOT_REQUESTED"
