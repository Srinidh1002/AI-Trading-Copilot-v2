import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "services" / "dashboard_read_models" / "dashboard_market_overview_view_v1.py",
    ROOT / "services" / "dashboard_read_models" / "dashboard_option_intelligence_view_v1.py",
    ROOT / "services" / "dashboard_read_models" / "dashboard_validation_summary_view_v1.py",
    ROOT / "services" / "dashboard_read_models" / "dashboard_decision_history_view_v1.py",
    ROOT / "services" / "dashboard_read_models" / "dashboard_runtime_operations_view_v1.py",
)


def modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_read_models_have_no_dashboard_or_authority_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "pandas",
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade",
        "services.paper_orchestration",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.performance",
        "services.performance_engine",
        "services.health",
        "services.refresh",
    )
    for path in FILES:
        for module in modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_read_models_generate_no_time_or_business_values():
    forbidden_tokens = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "calculate_pnl",
        "get_market_snapshot",
        "health_check.run",
        "get_trade_statistics",
    )
    for path in FILES:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.name}: {token}"
