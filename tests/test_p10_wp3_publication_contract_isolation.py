import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "dashboard_publication"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_publication_contracts_have_no_runtime_ui_or_persistence_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "time",
        "uuid",
        "random",
        "services.continuous_paper_trading_runtime",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )

    for path in PACKAGE.glob("*.py"):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_publication_contracts_generate_no_time_or_identity():
    forbidden_tokens = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
    )

    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.name}: {token}"


def test_public_api_is_explicit():
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
