import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(source(path), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def test_dashboard_inventory_matches_audited_baseline():
    expected = {
        "__init__.py",
        "cards.py",
        "charts.py",
        "dashboard_v2.py",
        "home.py",
        "layout.py",
        "live_market_test.py",
        "sidebar.py",
        "styles.py",
        "widgets.py",
    }

    actual = {
        path.name
        for path in DASHBOARD.glob("*.py")
    }

    assert expected.issubset(actual)


def test_active_application_targets_dashboard_v2():
    app_source = source(ROOT / "app.py")

    assert "from dashboard.dashboard_v2 import home" in app_source
    assert "from dashboard.home import home" not in app_source


def test_empty_dashboard_modules_have_no_authority():
    for name in ("__init__.py", "cards.py", "styles.py"):
        assert source(DASHBOARD / name).strip() == ""


def test_audit_records_current_active_dashboard_debt():
    active = source(DASHBOARD / "dashboard_v2.py")

    required_current_dependencies = {
        "sqlite3",
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade.paper_trade_manager",
        "services.refresh.refresh_intervals",
        "services.refresh",
        "services.health",
    }

    assert required_current_dependencies.issubset(
        imported_modules(DASHBOARD / "dashboard_v2.py")
    )
    assert "get_market_snapshot" in active
    assert "dashboard_analysis_service.analyse" in active
    assert "sqlite3.connect" in active
    assert "get_trade_statistics" in active
    assert "health_check.run" in active


def test_legacy_dashboard_pages_are_not_the_active_entrypoint():
    app_source = source(ROOT / "app.py")

    assert "dashboard.home" not in app_source
    assert "dashboard.live_market_test" not in app_source


def test_audit_documents_name_the_authoritative_p7_p8_p9_sources():
    audit = source(ROOT / "docs" / "P10A_DASHBOARD_AUDIT.md")

    assert "PaperTradePersistenceService" in audit
    assert "PaperPortfolioPersistenceService" in audit
    assert "PaperOrchestrationCycleResultV1" in audit
    assert "ContinuousPaperTradingRuntime.get_stats()" in audit
