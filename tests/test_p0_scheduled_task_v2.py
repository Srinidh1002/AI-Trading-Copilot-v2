"""Part 18 — Scheduled Task scripts must invoke ONLY the canonical preflight.

Static source inspection. No Windows task is registered or enabled by
any test in this file. P_SCHEDULED_TASK_REGISTERED remains False.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

START_SCRIPT = REPO / "tools" / "start_supervisor_if_fresh.ps1"
INSTALL_SCRIPT = REPO / "tools" / "install_supervisor_task.ps1"


def test_start_script_exists():
    assert START_SCRIPT.is_file()


def test_install_script_exists():
    assert INSTALL_SCRIPT.is_file()


def test_start_script_invokes_preflight():
    src = START_SCRIPT.read_text(encoding="utf-8")
    assert "preflight_and_start_five_market_paper.py" in src


def test_start_script_does_not_invoke_supervisor_module_directly():
    src = START_SCRIPT.read_text(encoding="utf-8")
    # Comment mentions are fine; an executable module call is not.
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "automated_paper_supervisor_v2" not in line, (
            f"start script must not invoke the supervisor directly: {line!r}"
        )


def test_start_script_has_no_inline_token_probe():
    src = START_SCRIPT.read_text(encoding="utf-8")
    # Preflight owns auth freshness. The script must not decode the JWT
    # itself or read FYERS_ACCESS_TOKEN for freshness.
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "FYERS_ACCESS_TOKEN" not in line, (
            f"start script must not read FYERS_ACCESS_TOKEN: {line!r}"
        )
        assert "decode_jwt" not in line
        assert "base64.urlsafe_b64decode" not in line


def test_start_script_never_automates_oauth():
    """No OAuth flow, browser, or callback in executable lines.

    Comment lines may describe that the operator ran fyers_daily_auth
    before this task fires; that is not automation.
    """
    src = START_SCRIPT.read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip().lower()
        if not stripped or stripped.startswith("#"):
            continue
        for bad in ("fyers_daily_auth", "webbrowser", "oauth", "callback"):
            assert bad not in stripped, (
                f"start script must not attempt OAuth flow: {bad!r} in {line!r}"
            )


def test_start_script_has_explicit_exit_code_propagation():
    src = START_SCRIPT.read_text(encoding="utf-8")
    assert "exit $rc" in src or "exit $LASTEXITCODE" in src


def test_install_script_points_at_start_script():
    src = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "start_supervisor_if_fresh.ps1" in src


def test_install_script_refuses_missing_start_script():
    src = INSTALL_SCRIPT.read_text(encoding="utf-8")
    # Must check that the target script exists before registering.
    assert "Test-Path $script" in src or "Missing scheduled-task entry script" in src


def test_no_test_ever_registers_a_task():
    """Static self-check: no other test file invokes task registration."""
    this_file = Path(__file__).resolve()
    tests_dir = REPO / "tests"
    for p in tests_dir.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if p.resolve() == this_file:
            continue
        src = p.read_text(encoding="utf-8")
        # Only flag executable invocation, not mentions in assertions.
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "assert" in stripped:
                continue
            assert "Register-ScheduledTask " not in stripped, (
                f"{p} invokes task registration: {line!r}"
            )
            assert "schtasks /create" not in stripped.lower(), (
                f"{p} invokes task registration: {line!r}"
            )
