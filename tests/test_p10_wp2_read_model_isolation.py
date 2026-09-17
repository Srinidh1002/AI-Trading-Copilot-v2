import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "dashboard_read_models"
FILES = (
    "dashboard_opportunity_view_v1.py",
    "dashboard_trade_plan_target_view_v1.py",
    "dashboard_trade_plan_view_v1.py",
    "dashboard_paper_fill_view_v1.py",
    "dashboard_paper_position_detail_view_v1.py",
)


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_wp2_contracts_have_no_ui_provider_or_authority_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "services.trade_planning",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.market",
        "services.execution",
    )

    for filename in FILES:
        for module in imports(PACKAGE / filename):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{filename}: {module}"


def test_wp2_contracts_generate_no_time_or_identity():
    forbidden = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
    )

    for filename in FILES:
        source = (PACKAGE / filename).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{filename}: {token}"


def test_wp2_contracts_are_exported():
    import services.dashboard_read_models as read_models

    for name in (
        "DashboardOpportunityViewV1",
        "DashboardTradePlanTargetViewV1",
        "DashboardTradePlanViewV1",
        "DashboardPaperFillViewV1",
        "DashboardPaperPositionDetailViewV1",
    ):
        assert name in read_models.__all__
        assert getattr(read_models, name) is not None
