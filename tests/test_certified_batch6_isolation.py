import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_monitoring_input_factory.py",
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_persistence_composition.py",
)


def test_batch6_has_no_order_methods_or_secret_access():
    for target in TARGETS:
        source = target.read_text(encoding="utf-8")
        for token in (
            "place_order(",
            "submit_order(",
            "modify_order(",
            "cancel_order(",
            "ANGEL_PIN",
            "ANGEL_TOTP_SECRET",
            "os.getenv(",
            "dotenv",
        ):
            assert token not in source, (target.name, token)


def test_batch6_has_no_legacy_trading_imports():
    forbidden = {
        "services.core.trading_engine",
        "services.testing.scenario_runner",
    }
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not modules.intersection(forbidden)
