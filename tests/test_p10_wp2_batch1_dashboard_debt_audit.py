from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP2_P6_P7_FIELD_AUDIT.md"
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


def test_active_dashboard_legacy_trade_plan_rendering_is_removed():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'st.subheader("💰 Trade Plan")' not in source
    assert 'trade["entry"]' not in source
    assert 'trade["stop_loss"]' not in source
    assert 'trade["target1"]' not in source
    assert 'trade["target2"]' not in source
    assert 'trade["risk"]["TARGET3"]' not in source
    assert 'trade["risk"]["RR"]' not in source

    assert "get_plan_position_views(st.session_state)" in source
    assert "render_plan_and_position_dashboard(" in source

def test_audit_rejects_legacy_trade_dictionary_as_authority():
    source = AUDIT.read_text(encoding="utf-8")

    assert "legacy `trade` dictionary" in source
    assert "must be replaced later" in source
    assert "second competing authority" in source


def test_active_dashboard_uses_the_wp2_read_model_boundary():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert (
        "from dashboard.dashboard_read_model_state "
        "import get_plan_position_views"
    ) in source
    assert (
        "from dashboard.plan_position_components "
        "import render_plan_and_position_dashboard"
    ) in source