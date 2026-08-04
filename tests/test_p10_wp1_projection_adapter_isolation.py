import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "services"
    / "dashboard_read_models"
    / "dashboard_projection_adapters.py"
)


def test_projection_adapters_are_read_only_and_ui_free():
    source = PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    forbidden = (
        "streamlit",
        "sqlite3",
        "services.market",
        "services.trade",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.execution",
    )

    for module in modules:
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module

    for token in (
        ".save(",
        ".update(",
        ".delete(",
        "datetime.now(",
        "uuid4(",
        "random.",
    ):
        assert token not in source
