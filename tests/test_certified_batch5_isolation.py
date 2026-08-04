import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_p5_normalization.py",
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_new_entry_input_factory.py",
)


def test_batch5_contains_no_order_methods_or_secrets():
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


def test_batch5_does_not_import_legacy_trading_engine():
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "services.core.trading_engine" not in modules
        assert "services.testing.scenario_runner" not in modules
