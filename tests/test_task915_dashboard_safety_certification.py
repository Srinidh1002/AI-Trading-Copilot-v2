"""Final bounded safety certification for Task 9.15 dashboard presentation."""
import ast
from pathlib import Path

import pytest

import dashboard.dashboard_v2 as dashboard_v2
from dashboard.dashboard_navigation import DASHBOARD_PAGES
from tests.test_task915_dashboard_application_view import view


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "dashboard_navigation.py", "dashboard_status_components.py", "data_health_components.py",
    "manual_live_planner_components.py", "markets_components.py",
    "recommendation_history_components.py", "task9_certification_components.py",
    "trade_now_components.py", "trades_pnl_components.py", "dashboard_publication_sync.py",
    "dashboard_read_model_state.py", "dashboard_v2.py",
)


def test_task915_components_have_no_execution_provider_or_counting_dependencies():
    forbidden_modules = ("angel", "broker", "repository", "task9_live_paper_certification_progress_builder", "task9_live_paper_trade_counting_evaluator", "services.execution")
    forbidden_calls = {"place_order", "submit_order", "modify_order", "cancel_order"}
    for name in FILES:
        tree = ast.parse((ROOT / "dashboard" / name).read_text(encoding="utf-8"))
        imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert not any(any(token in module for token in forbidden_modules) for module in imports), name
        calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))}
        assert forbidden_calls.isdisjoint(calls), name
        source = (ROOT / "dashboard" / name).read_text(encoding="utf-8")
        assert "datetime.now(" not in source and "time.time(" not in source


@pytest.mark.parametrize("page,expected", tuple(zip(DASHBOARD_PAGES, ("trade", "markets", "trades", "certification", "planner", "health"))))
def test_all_six_pages_dispatch_headlessly_without_mutating_published_view(monkeypatch, page, expected):
    published = view("safety-view")
    calls = []
    class Side:
        def radio(self, *args, **kwargs): return page
    class St:
        def __init__(self): self.session_state={"dashboard_application_view_v1": published}; self.sidebar=Side()
        def title(self, *a): pass
        def caption(self, *a): pass
        def divider(self): pass
        def subheader(self, *a): pass
        def info(self, *a): pass
        def write(self, *a): pass
        def warning(self, *a): pass
    st=St()
    monkeypatch.setattr(dashboard_v2, "st", st)
    monkeypatch.setattr(dashboard_v2, "synchronize_registered_dashboard_publication", lambda state: False)
    monkeypatch.setattr(dashboard_v2, "get_operator_application_view_model", lambda state: None)
    for attr, label in (("render_trade_now_dashboard","trade"),("render_markets_comparison","markets"),("render_recommendation_history","markets"),("render_trades_pnl_center","trades"),("render_task9_certification_center","certification"),("render_manual_live_planner","planner"),("render_dashboard_status","health"),("render_data_health_strip","health")):
        monkeypatch.setattr(dashboard_v2, attr, lambda *a, _label=label, **k: calls.append(_label))
    dashboard_v2.home()
    assert expected in calls
    assert published.execution_mode == "PAPER" and published.broker_order_submission is False and published.live_execution_eligible is False
