"""Read-only dashboard refresh configuration regressions."""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_uses_native_low_cadence_fragment_refresh_without_manual_reruns():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["DASHBOARD_AUTO_REFRESH_SECONDS"] == 15
    assert "@st.fragment(run_every=DASHBOARD_AUTO_REFRESH_SECONDS)" in source
    assert "def _render_dashboard" in source and "home()" in source
    assert "st.rerun(" not in source and "sleep(" not in source


def test_dashboard_refresh_configuration_remains_read_only_and_paper_safe():
    source = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("app.py", "dashboard/dashboard_v2.py", "dashboard/task9_certification_components.py")
    )
    for forbidden in (
        "Angel", "place_order", "submit_order", "Task9LivePaperCertificationLauncher",
        "requests.", "httpx.", "socket.", "broker_order_submission=True",
        "live_execution_eligible=True",
    ):
        assert forbidden not in source
    assert "PAPER CERTIFICATION MODE · PAPER ONLY · BROKER ORDER SUBMISSION DISABLED" in (
        ROOT / "dashboard" / "dashboard_v2.py"
    ).read_text(encoding="utf-8")
