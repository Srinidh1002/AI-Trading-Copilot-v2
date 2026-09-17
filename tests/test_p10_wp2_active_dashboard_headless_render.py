import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "dashboard_v2.py"


def test_certified_section_reads_then_renders_without_computation():
    source = DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id
        in {
            "get_plan_position_views",
            "render_plan_and_position_dashboard",
        }
    ]

    assert len(
        [
            node
            for node in calls
            if node.func.id == "get_plan_position_views"
        ]
    ) == 1
    assert len(
        [
            node
            for node in calls
            if node.func.id == "render_plan_and_position_dashboard"
        ]
    ) == 1


def test_certified_renderer_receives_only_view_variables():
    source = DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)

    render_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "render_plan_and_position_dashboard"
    )

    keyword_values = {
        keyword.arg: keyword.value.id
        for keyword in render_call.keywords
        if isinstance(keyword.value, ast.Name)
    }

    assert keyword_values == {
        "opportunity": "opportunity_view",
        "plan": "trade_plan_view",
        "position": "paper_position_view",
    }
