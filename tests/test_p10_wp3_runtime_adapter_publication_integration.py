from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "continuous_runtime_adapter.py"
)


def test_runtime_adapter_accepts_optional_publication_boundary():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "dashboard_publication_producer" in source
    assert "dashboard_publication_store" in source
    assert "must be configured together" in source


def test_opportunity_and_monitoring_results_are_offered_to_producer():
    source = ADAPTER.read_text(encoding="utf-8")

    assert source.count("self._publish_cycle_result(") == 2
    assert 'source="OPPORTUNITY"' in source
    assert 'source="MONITORING"' in source


def test_runtime_adapter_exposes_read_only_publication_snapshot():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "def get_dashboard_publication_snapshot(self):" in source
    assert "return self.dashboard_publication_store.get_snapshot()" in source
