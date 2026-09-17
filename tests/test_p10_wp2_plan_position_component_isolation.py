import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "dashboard" / "plan_position_components.py"


def imported_modules() -> set[str]:
    tree = ast.parse(PATH.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_components_import_read_models_only_from_services():
    modules = imported_modules()

    service_imports = {
        item for item in modules if item == "services" or item.startswith("services.")
    }
    assert service_imports == {"services.dashboard_read_models"}


def test_components_have_no_business_or_persistence_imports():
    forbidden = (
        "sqlite3",
        "pandas",
        "services.market",
        "services.trade",
        "services.trade_planning",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.execution",
    )

    for module in imported_modules():
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_components_have_no_trade_computation_tokens():
    source = PATH.read_text(encoding="utf-8")

    for token in (
        "risk_reward",
        "calculate_pnl",
        "evaluate_entry",
        "evaluate_stop",
        "evaluate_target",
        "sqlite3.connect",
        "get_market_snapshot",
        "DashboardAnalysisService",
    ):
        assert token not in source
