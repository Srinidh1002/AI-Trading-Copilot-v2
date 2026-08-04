import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "services" / "dashboard_read_models" / "dashboard_option_intelligence_projection.py",
    ROOT / "services" / "dashboard_read_models" / "dashboard_runtime_operations_projection.py",
)


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_projections_have_no_ui_provider_persistence_or_execution_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "pandas",
        "services.market_snapshot",
        "services.trade",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.performance",
        "services.health",
        "services.refresh",
    )
    for path in FILES:
        for module in imports(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_projections_generate_no_authoritative_values():
    forbidden = (
        "datetime.now(",
        "time.time(",
        "uuid4(",
        "calculate_pnl",
        "health_check.run",
        "get_market_snapshot",
        "get_trade_statistics",
    )
    for path in FILES:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name}: {token}"
