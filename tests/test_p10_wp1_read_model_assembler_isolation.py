import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "services"
    / "dashboard_read_models"
    / "dashboard_read_model_assembler.py"
)


def test_assembler_has_no_provider_persistence_or_ui_imports():
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


def test_assembler_generates_no_identity_or_time():
    source = PATH.read_text(encoding="utf-8")

    for token in (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
    ):
        assert token not in source
