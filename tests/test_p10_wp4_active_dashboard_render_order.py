from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


def test_publication_sync_precedes_all_state_reads():
    source = DASHBOARD.read_text(encoding="utf-8")

    sync_index = source.index(
        "synchronize_registered_dashboard_publication("
    )
    plan_index = source.index(
        "get_plan_position_views(st.session_state)"
    )
    operations_index = source.index(
        "get_operational_views(st.session_state)"
    )

    assert sync_index < plan_index
    assert sync_index < operations_index


def test_certified_plan_and_operations_are_rendered_once():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert source.count("render_plan_and_position_dashboard(") == 1
    assert source.count("render_operational_dashboard(") == 1
