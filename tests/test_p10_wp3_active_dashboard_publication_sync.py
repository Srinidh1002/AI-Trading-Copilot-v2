from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"
SYNC = ROOT / "dashboard" / "dashboard_publication_sync.py"
ADAPTER = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "continuous_runtime_adapter.py"
)


def test_active_dashboard_synchronizes_before_reading_views():
    source = DASHBOARD.read_text(encoding="utf-8")

    sync_index = source.index(
        "synchronize_registered_dashboard_publication("
    )
    read_index = source.index(
        "get_plan_position_views(st.session_state)"
    )

    assert sync_index < read_index


def test_active_dashboard_does_not_import_runtime_or_orchestration():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "ContinuousPaperTradingRuntime" not in source
    assert "ContinuousPaperOrchestrationRuntimeAdapter" not in source
    assert "DeterministicPaperOrchestrationCycleCoordinator" not in source


def test_sync_reads_registry_and_reuses_existing_sync_boundary():
    source = SYNC.read_text(encoding="utf-8")

    assert "get_registered_dashboard_publication_snapshot()" in source
    assert "return synchronize_dashboard_publication(state, snapshot)" in source


def test_runtime_adapter_registers_configured_store():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "register_dashboard_publication_store(" in source
    assert "if dashboard_publication_store is not None:" in source
