"""Static architecture boundaries for legacy research-only modules."""
from __future__ import annotations

import ast
from pathlib import Path


_TASK9_SURFACE = (
    "services/certification/task9_live_paper_certification_launcher.py",
    "services/certification/task9_live_paper_production_composition.py",
    "services/certification/task9_production_child_evidence_authority.py",
    "services/certification/task8_live_paper_default_composition.py",
    "services/paper_orchestration/certified_runtime_composition.py",
    "services/dashboard_publication/task9_dashboard_publication_publisher.py",
    "services/dashboard_read_models/task9_dashboard_shell.py",
)


def _imports(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }


def test_task9_surface_excludes_legacy_research_execution_and_archive_modules():
    forbidden_prefixes = (
        "services.market_data",
        "dashboard.home",
        "services.core.trading_engine",
        "services.execution.order_manager",
        "services.completed_candle_service",
        "services.market.historical_market",
        "archive",
        "Day1_Snapshots",
        "services.analysis.option_chain",
    )
    imports = set().union(*(_imports(path) for path in _TASK9_SURFACE))
    assert not any(
        imported.startswith(prefix)
        for imported in imports
        for prefix in forbidden_prefixes
    )


def test_current_streamlit_entrypoint_uses_task9_dashboard_not_legacy_home():
    assert "from dashboard.dashboard_v2 import home" in Path("app.py").read_text(
        encoding="utf-8"
    )
    assert "dashboard.home" not in _imports("app.py")
