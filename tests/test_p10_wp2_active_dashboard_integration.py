import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"
STATE = ROOT / "dashboard" / "dashboard_read_model_state.py"


def test_active_dashboard_imports_certified_renderer_and_state_reader():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert (
        "from dashboard.dashboard_read_model_state "
        "import get_plan_position_views"
    ) in source
    assert (
        "from dashboard.plan_position_components "
        "import render_plan_and_position_dashboard"
    ) in source


def test_active_dashboard_replaces_legacy_trade_plan_block():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'st.subheader("💰 Trade Plan")' not in source
    assert 'trade["entry"]' not in source
    assert 'trade["stop_loss"]' not in source
    assert 'trade["target1"]' not in source
    assert 'trade["target2"]' not in source
    assert 'trade["risk"]["TARGET3"]' not in source
    assert 'trade["risk"]["RR"]' not in source

    assert "get_plan_position_views(st.session_state)" in source
    assert "render_plan_and_position_dashboard(" in source


def test_state_boundary_imports_read_models_only_from_services():
    tree = ast.parse(STATE.read_text(encoding="utf-8"))
    service_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            service_modules.update(
                alias.name
                for alias in node.names
                if alias.name == "services"
                or alias.name.startswith("services.")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (
                node.module == "services"
                or node.module.startswith("services.")
            )
        ):
            service_modules.add(node.module)

    assert service_modules == {"services.dashboard_read_models"}


def test_state_boundary_has_no_business_or_persistence_calls():
    source = STATE.read_text(encoding="utf-8")

    for token in (
        "get_market_snapshot",
        "DashboardAnalysisService",
        "sqlite3",
        "PaperTradePersistenceService",
        "PaperPortfolioPersistenceService",
        "execute_p6_planning_stage",
        "NewEntryPaperLifecycleExecutor",
        "datetime.now(",
        "uuid4(",
    ):
        assert token not in source
