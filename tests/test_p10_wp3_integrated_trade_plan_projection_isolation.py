import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECTION = (
    ROOT
    / "services"
    / "dashboard_read_models"
    / "dashboard_integrated_trade_plan_projection.py"
)
PRODUCER = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_runtime_publication_producer.py"
)


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_projection_has_no_planning_or_lifecycle_authorities():
    forbidden = (
        "streamlit",
        "sqlite3",
        "services.trade_planning",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )
    for module in imports(PROJECTION):
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_producer_has_no_streamlit_or_persistence_service_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )
    for module in imports(PRODUCER):
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_producer_uses_caller_owned_clock_and_identity_factory():
    source = PRODUCER.read_text(encoding="utf-8")

    assert "publication_id_factory" in source
    assert "_aware(self.clock)" in source
    assert "datetime.now(" not in source
    assert "uuid4(" not in source
