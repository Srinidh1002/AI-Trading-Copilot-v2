import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_publication_store.py"
)


def imported_modules():
    tree = ast.parse(STORE.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_store_has_lock_but_no_runtime_ui_or_persistence_imports():
    modules = imported_modules()

    assert "threading" in modules

    forbidden = (
        "streamlit",
        "sqlite3",
        "services.continuous_paper_trading_runtime",
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


def test_store_generates_no_time_or_identity():
    source = STORE.read_text(encoding="utf-8")

    for token in (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
    ):
        assert token not in source


def test_public_api_exports_store():
    import services.dashboard_publication as publication

    assert tuple(publication.__all__) == (
        "DashboardPublicationBuildInputV1",
        "DashboardPublicationEnvelopeV1",
        "DashboardPublicationService",
        "DashboardPublicationSnapshotV1",
        "DashboardPublicationStore",
        "clear_dashboard_publication_store_registration",
        "get_registered_dashboard_publication_snapshot",
        "register_dashboard_publication_store",
    )
