import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "dashboard_read_models"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_complete_read_model_package_is_streamlit_free():
    for path in PACKAGE.glob("*.py"):
        assert "streamlit" not in imported_modules(path), path.name


def test_complete_read_model_package_has_no_mutable_authority_imports():
    forbidden = (
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade.paper_trade_manager",
        "services.paper_trading",
        "services.paper_portfolio",
        "services.paper_orchestration",
        "services.execution",
        "services.live",
    )

    for path in PACKAGE.glob("*.py"):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_complete_read_model_package_has_no_hidden_nondeterminism():
    forbidden_tokens = (
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "uuid4(",
        "random.",
        "secrets.",
    )

    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.name}: {token}"


def test_wp1_certification_document_records_deferred_ui_migration():
    source = (
        ROOT / "docs" / "P10_WP1_CERTIFICATION.md"
    ).read_text(encoding="utf-8")

    assert "does not migrate the active Streamlit page yet" in source
    assert "P10-WP1 is complete" in source
    assert "enable live execution" in source
