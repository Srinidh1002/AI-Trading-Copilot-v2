import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_live_read_authorities.py"
)


def test_authority_module_has_no_order_or_legacy_imports():
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
        "services.paper",
        "services.paper_trading",
    )
    for module in modules:
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_authority_module_contains_no_order_methods_or_secrets():
    source = TARGET.read_text(encoding="utf-8")
    for token in (
        "place_order(",
        "submit_order(",
        "modify_order(",
        "cancel_order(",
        "ANGEL_PIN",
        "ANGEL_TOTP_SECRET",
        "API_KEY",
        "PASSWORD",
    ):
        assert token not in source
