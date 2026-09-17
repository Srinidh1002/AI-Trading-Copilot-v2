import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = tuple(
    ROOT / "services" / "paper_orchestration" / name
    for name in (
        "certified_dashboard_composition.py",
        "certified_operator_controls.py",
        "certified_runtime_logging.py",
        "certified_runtime_launcher.py",
    )
)


def test_batch7_has_no_order_methods_or_secret_reads():
    for target in TARGETS:
        source = target.read_text(encoding="utf-8")
        for token in (
            "place_order(",
            "submit_order(",
            "modify_order(",
            "cancel_order(",
            "os.getenv(",
            "dotenv",
            "ANGEL_PIN",
            "ANGEL_TOTP_SECRET",
        ):
            assert token not in source, (target.name, token)


def test_batch7_has_no_legacy_trading_imports():
    forbidden = {
        "services.core.trading_engine",
        "services.testing.scenario_runner",
        "services.paper_trading_runtime_adapter",
    }
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not modules.intersection(forbidden)
