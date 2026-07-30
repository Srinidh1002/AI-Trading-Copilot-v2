import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "dashboard" / "plan_position_components.py"
STATE = ROOT / "dashboard" / "dashboard_read_model_state.py"
ACTIVE = ROOT / "dashboard" / "dashboard_v2.py"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_wp2_components_and_state_boundary_are_read_only():
    forbidden = (
        "sqlite3",
        "pandas",
        "requests",
        "yfinance",
        "services.market",
        "services.trade",
        "services.trade_planning",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.execution",
    )

    for path in (COMPONENTS, STATE):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_active_dashboard_has_one_certified_plan_position_renderer():
    source = ACTIVE.read_text(encoding="utf-8")

    assert source.count("render_plan_and_position_dashboard(") == 1
    assert source.count("get_plan_position_views(st.session_state)") == 1


def test_active_dashboard_has_no_legacy_plan_authority_tokens():
    source = ACTIVE.read_text(encoding="utf-8")

    for token in (
        'trade["entry"]',
        'trade["stop_loss"]',
        'trade["target1"]',
        'trade["target2"]',
        'trade["risk"]["TARGET3"]',
        'trade["risk"]["RR"]',
    ):
        assert token not in source


def test_wp2_boundary_generates_no_hidden_time_or_identity():
    for path in (COMPONENTS, STATE):
        source = path.read_text(encoding="utf-8")
        for token in (
            "datetime.now(",
            "datetime.utcnow(",
            "time.time(",
            "uuid4(",
            "random.",
        ):
            assert token not in source, f"{path.name}: {token}"
