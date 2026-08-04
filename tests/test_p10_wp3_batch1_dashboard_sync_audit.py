from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP3_RUNTIME_PUBLICATION_AUDIT.md"
STATE = ROOT / "dashboard" / "dashboard_read_model_state.py"
ACTIVE = ROOT / "dashboard" / "dashboard_v2.py"


def test_dashboard_state_keys_are_recorded():
    source = AUDIT.read_text(encoding="utf-8")

    for key in (
        "dashboard_opportunity_view_v1",
        "dashboard_trade_plan_view_v1",
        "dashboard_paper_position_detail_view_v1",
    ):
        assert key in source


def test_current_state_reader_has_no_runtime_sync():
    source = STATE.read_text(encoding="utf-8")

    assert "ContinuousPaperTradingRuntime" not in source
    assert "DashboardPublicationStore" not in source
    assert "synchronize" not in source.lower()


def test_active_dashboard_only_reads_current_session_state():
    source = ACTIVE.read_text(encoding="utf-8")

    assert "get_plan_position_views(st.session_state)" in source
    assert "DashboardPublicationStore" not in source
    assert "ContinuousPaperTradingRuntime" not in source


def test_audit_requires_streamlit_to_remain_read_only():
    source = AUDIT.read_text(encoding="utf-8")

    assert "Streamlit never invokes orchestration" in source
    assert "Streamlit reads" in source
    assert "DashboardSessionStateSynchronizer" in source
