from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_runtime_publication_producer.py"
)


def test_runtime_producer_projects_wp4_sources():
    source = PRODUCER.read_text(encoding="utf-8")

    assert "project_option_intelligence(" in source
    assert "project_runtime_operations(" in source
    assert "option_chain_intelligence" in source
    assert "option_intelligence=option_intelligence" in source
    assert "runtime_operations=runtime_operations" in source
