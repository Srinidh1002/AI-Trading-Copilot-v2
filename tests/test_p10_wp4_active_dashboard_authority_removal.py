import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"
APP = ROOT / "app.py"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_active_dashboard_imports_only_ui_config_and_read_boundaries():
    allowed_prefixes = (
        "streamlit",
        "config",
        "dashboard.dashboard_operational_read_model_state",
        "dashboard.dashboard_publication_sync",
        "dashboard.dashboard_read_model_state",
        "dashboard.operational_components",
        "dashboard.plan_position_components",
    )

    for module in imported_modules(DASHBOARD):
        assert any(
            module == item or module.startswith(item + ".")
            for item in allowed_prefixes
        ), module


def test_active_dashboard_has_no_fragment_or_refresh_authority():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "@st.fragment" not in source
    assert "run_every" not in source
    assert "MARKET_SNAPSHOT" not in source


def test_unavailable_sections_are_explicit():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "Certified market-overview data is not available yet" in source
    assert "Certified portfolio validation statistics are not available yet" in source
    assert "Certified typed decision history is not available yet" in source


def test_app_has_no_live_market_import():
    source = APP.read_text(encoding="utf-8")

    assert "live_multi_timeframe_data" not in source
    assert "services.market" not in source
    assert "from dashboard.dashboard_v2 import home" in source
