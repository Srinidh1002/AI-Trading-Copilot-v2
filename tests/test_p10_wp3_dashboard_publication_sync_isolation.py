import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "dashboard" / "dashboard_publication_sync.py"


def imported_modules():
    tree = ast.parse(SYNC.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_sync_has_no_streamlit_runtime_or_persistence_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "threading",
        "services.continuous_paper_trading_runtime",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.execution",
    )

    for module in imported_modules():
        assert not any(
            module == item or module.startswith(item + ".")
            for item in forbidden
        ), module


def test_sync_performs_no_projection_or_trading_computation():
    source = SYNC.read_text(encoding="utf-8")

    for token in (
        "project_trade_opportunity",
        "project_three_target_trade_plan",
        "project_paper_trade_position_detail",
        "calculate_pnl",
        "evaluate_entry",
        "evaluate_stop",
        "evaluate_target",
        "datetime.now(",
        "uuid4(",
    ):
        assert token not in source


def test_sync_writes_exact_wp2_state_keys():
    source = SYNC.read_text(encoding="utf-8")

    for token in (
        "OPPORTUNITY_STATE_KEY",
        "TRADE_PLAN_STATE_KEY",
        "PAPER_POSITION_STATE_KEY",
    ):
        assert token in source
