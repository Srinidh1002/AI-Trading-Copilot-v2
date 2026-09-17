import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_live_provider_readers.py",
    ROOT
    / "services"
    / "paper_orchestration"
    / "certified_p6_input_factory.py",
)


def test_batch4_has_no_order_methods_or_secret_access():
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


def test_p6_factory_does_not_import_legacy_live_pipeline():
    target = TARGETS[1]
    tree = ast.parse(target.read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "services.live_option_decision_pipeline" not in modules
    assert "services.live_analysis_pipeline" not in modules
    assert "services.core.trading_engine" not in modules
