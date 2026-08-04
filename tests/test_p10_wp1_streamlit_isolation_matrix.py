import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def imports(path: Path) -> set[str]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )
    result: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)

    return result


def test_presentation_helpers_do_not_import_services():
    helpers = (
        "charts.py",
        "layout.py",
        "sidebar.py",
        "widgets.py",
    )

    for name in helpers:
        assert not any(
            module == "services"
            or module.startswith("services.")
            for module in imports(DASHBOARD / name)
        ), name


def test_dashboard_tree_has_no_live_order_authority_imports():
    forbidden_prefixes = (
        "services.execution.order_executor",
        "services.execution.order_manager",
        "services.live.live_market_engine",
    )

    for path in DASHBOARD.glob("*.py"):
        modules = imports(path)
        for prefix in forbidden_prefixes:
            assert not any(
                module == prefix or module.startswith(prefix + ".")
                for module in modules
            ), f"{path.name}: {prefix}"


def test_read_model_design_forbids_streamlit_and_provider_imports():
    design = (
        ROOT
        / "docs"
        / "P10_READ_MODEL_DESIGN.md"
    ).read_text(encoding="utf-8")

    for token in (
        "streamlit",
        "provider or network clients",
        "broker clients",
        "order executors or order managers",
        "sqlite3",
        "random or UUID generation",
    ):
        assert token in design


def test_read_model_design_requires_paper_only_flags():
    design = (
        ROOT
        / "docs"
        / "P10_READ_MODEL_DESIGN.md"
    ).read_text(encoding="utf-8")

    assert "execution_mode" in design
    assert "live_execution_eligible" in design
    assert "PAPER-only flags enforced" in design


def test_read_model_design_requires_caller_supplied_identity_and_time():
    design = (
        ROOT
        / "docs"
        / "P10_READ_MODEL_DESIGN.md"
    ).read_text(encoding="utf-8")

    assert "caller-supplied time" in design
    assert "caller-supplied identity" in design
