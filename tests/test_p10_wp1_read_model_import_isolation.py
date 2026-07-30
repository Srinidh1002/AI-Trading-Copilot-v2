import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "dashboard_read_models"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_read_model_package_has_no_forbidden_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "requests",
        "yfinance",
        "random",
        "uuid",
        "services.execution",
        "services.live",
        "services.market",
        "services.trade",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
    )

    for path in PACKAGE.glob("*.py"):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_read_model_package_does_not_generate_current_time():
    forbidden_tokens = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
    )

    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.name}: {token}"


def test_public_exports_are_explicit():
    import services.dashboard_read_models as read_models

    assert set(read_models.__all__) == {
        "DashboardCycleViewV1",
        "DashboardMarketStateV1",
        "DashboardOpportunityViewV1",
        "DashboardPaperFillViewV1",
        "DashboardPaperPositionDetailViewV1",
        "DashboardPaperPositionViewV1",
        "DashboardPortfolioViewV1",
        "DashboardReadModelAssembler",
        "DashboardReadModelAssemblyInputV1",
        "DashboardRunnerHealthV1",
        "DashboardSystemSnapshotV1",
        "DashboardTradePlanTargetViewV1",
        "DashboardTradePlanViewV1",
        "DashboardValidationSummaryV1",
        "project_cycle_result",
        "project_paper_trade_fill",
        "project_paper_trade_position_detail",
        "project_paper_trade_snapshot",
        "project_portfolio_snapshot",
        "project_runtime_stats",
        "project_three_target_trade_plan",
        "project_trade_opportunity",
    }
