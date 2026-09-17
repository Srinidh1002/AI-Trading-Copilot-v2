import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_publication_registry.py"
)
SYNC = ROOT / "dashboard" / "dashboard_publication_sync.py"
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"
CERT = ROOT / "docs" / "P10_WP3_CERTIFICATION.md"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_registry_has_lock_without_ui_or_orchestration_imports():
    modules = imported_modules(REGISTRY)

    assert "threading" in modules
    forbidden = (
        "streamlit",
        "sqlite3",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )
    for module in modules:
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_sync_and_registry_generate_no_time_or_identity():
    for path in (REGISTRY, SYNC):
        source = path.read_text(encoding="utf-8")
        for token in (
            "datetime.now(",
            "datetime.utcnow(",
            "time.time(",
            "uuid4(",
            "random.",
        ):
            assert token not in source, f"{path.name}: {token}"


def test_active_dashboard_has_single_publication_sync_call():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert source.count(
        "synchronize_registered_dashboard_publication("
    ) == 1


def test_certification_keeps_live_execution_disabled():
    source = CERT.read_text(encoding="utf-8")

    assert "PAPER-only" in source
    assert "enable LIVE execution" in source
    assert "no broker order placement" in source
