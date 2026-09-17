import ast
from pathlib import Path


TARGET = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "paper_orchestration"
    / "certified_runtime_composition.py"
)


def test_composition_has_no_order_submission_methods():
    source = TARGET.read_text(encoding="utf-8")
    for token in (
        "place_order(",
        "submit_order(",
        "modify_order(",
        "cancel_order(",
        "ENABLE_LIVE_TRADING = True",
        'execution_mode="LIVE"',
        "live_execution_eligible=True",
    ):
        assert token not in source


def test_composition_has_no_legacy_trading_authority_imports():
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    forbidden = {
        "services.core.trading_engine",
        "services.testing.scenario_runner",
        "services.paper_trading_runtime_adapter",
    }
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not modules.intersection(forbidden)
