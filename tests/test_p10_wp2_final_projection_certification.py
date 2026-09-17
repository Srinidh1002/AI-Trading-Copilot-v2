from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (
    ROOT
    / "services"
    / "dashboard_read_models"
    / "dashboard_plan_position_projection_adapters.py"
)
DOC = ROOT / "docs" / "P10_WP2_CERTIFICATION.md"


def test_projection_uses_persisted_pnl_priority():
    source = ADAPTERS.read_text(encoding="utf-8")

    assert "pnl.realized_net_pnl_after" in source
    assert "pnl.unrealized_pnl_after" in source
    assert "pnl.total_pnl_after" in source
    assert "position.realized_net_pnl" in source
    assert "position.unrealized_pnl" in source
    assert "position.total_pnl" in source


def test_projection_preserves_entry_then_exit_fill_order():
    source = ADAPTERS.read_text(encoding="utf-8")

    assert "project_paper_trade_fill(position.entry_fill)" in source
    assert "for item in position.exit_fills" in source


def test_certification_records_deferred_legacy_dashboard_debt():
    source = DOC.read_text(encoding="utf-8")

    for item in (
        "market snapshot acquisition",
        "dashboard analysis invocation",
        "SQLite decision-history reads",
        "legacy validation statistics",
    ):
        assert item in source


def test_certification_explicitly_keeps_live_execution_disabled():
    source = DOC.read_text(encoding="utf-8")

    assert "LIVE execution is not enabled" in source
    assert "PAPER-only flags are preserved" in source
