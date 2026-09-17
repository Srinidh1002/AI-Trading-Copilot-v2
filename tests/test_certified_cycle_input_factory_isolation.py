import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_cycle_input_factory.py"
)


def test_factory_imports_only_contract_boundaries():
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    forbidden = (
        "services.broker",
        "services.core.trading_engine",
        "services.testing.scenario_runner",
        "services.live_analysis_pipeline",
        "services.live_option_decision_pipeline",
        "services.paper",
        "services.paper_trading",
    )
    for module in modules:
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_factory_contains_no_order_methods_or_secret_access():
    source = TARGET.read_text(encoding="utf-8")
    for token in (
        "place_order(",
        "submit_order(",
        "modify_order(",
        "cancel_order(",
        "os.getenv(",
        ".env",
        "ANGEL_PIN",
        "ANGEL_TOTP_SECRET",
    ):
        assert token not in source
