import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "dashboard" / "dashboard_operational_read_model_state.py",
    ROOT / "dashboard" / "operational_components.py",
)


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_components_have_no_legacy_or_runtime_authority_imports():
    forbidden = (
        "streamlit",
        "sqlite3",
        "pandas",
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade",
        "services.paper_orchestration",
        "services.performance",
        "services.performance_engine",
        "services.health",
        "services.refresh",
    )

    for path in FILES:
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_components_perform_no_analysis_or_acquisition():
    forbidden = (
        "get_market_snapshot",
        "DashboardAnalysisService",
        "dashboard_trade_presentation",
        "get_trade_statistics",
        "health_check.run",
        "calculate_pnl",
        "datetime.now(",
        "time.time(",
    )

    for path in FILES:
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name}: {token}"
