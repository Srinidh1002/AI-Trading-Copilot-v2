import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = (
    ROOT
    / "services"
    / "dashboard_publication"
    / "dashboard_publication_envelope_v1.py"
)
SYNC = ROOT / "dashboard" / "dashboard_publication_sync.py"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_envelope_and_sync_have_no_legacy_authority_imports():
    forbidden = (
        "sqlite3",
        "pandas",
        "services.market_snapshot",
        "services.dashboard.dashboard_analysis_service",
        "services.trade",
        "services.performance",
        "services.performance_engine",
        "services.health",
        "services.refresh",
    )
    for path in (ENVELOPE, SYNC):
        for module in imported_modules(path):
            assert not any(
                module == item or module.startswith(item + ".")
                for item in forbidden
            ), f"{path.name}: {module}"


def test_sync_uses_exact_wp4_state_keys():
    source = SYNC.read_text(encoding="utf-8")
    assert "dashboard_option_intelligence_view_v1" in source
    assert "dashboard_runtime_operations_view_v1" in source
