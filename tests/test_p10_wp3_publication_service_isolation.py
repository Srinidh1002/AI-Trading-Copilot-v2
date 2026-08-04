import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_publication_service.py"
)
BUILD_INPUT = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_publication_build_input_v1.py"
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_service_has_no_runtime_ui_or_persistence_authority():
    forbidden = (
        "streamlit",
        "sqlite3",
        "threading",
        "time",
        "uuid",
        "random",
        "services.continuous_paper_trading_runtime",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )

    for path in (SERVICE, BUILD_INPUT):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_service_only_uses_existing_projection_adapters():
    source = SERVICE.read_text(encoding="utf-8")

    for token in (
        "project_trade_opportunity",
        "project_three_target_trade_plan",
        "project_paper_trade_position_detail",
    ):
        assert token in source


def test_service_generates_no_time_identity_or_trading_values():
    for path in (SERVICE, BUILD_INPUT):
        source = path.read_text(encoding="utf-8")
        for token in (
            "datetime.now(",
            "datetime.utcnow(",
            "time.time(",
            "uuid4(",
            "random.",
            "calculate_pnl",
            "evaluate_entry",
            "evaluate_stop",
            "evaluate_target",
        ):
            assert token not in source, f"{path.name}: {token}"


def test_public_api_includes_service_boundary():
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
