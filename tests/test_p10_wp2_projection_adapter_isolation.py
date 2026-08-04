import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "services"
    / "dashboard_read_models"
    / "dashboard_plan_position_projection_adapters.py"
)


def test_adapters_have_no_ui_or_mutable_service_imports():
    tree = ast.parse(PATH.read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

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

    for module in modules:
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_adapters_do_not_generate_time_identity_or_pnl():
    source = PATH.read_text(encoding="utf-8")

    for token in (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
        "sum(fill.net_cash_effect",
        "sum(item.net_cash_effect",
    ):
        assert token not in source
