from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = tuple((ROOT / "scripts" / name) for name in ("paper_preflight.ps1", "paper_canary.ps1", "paper_run_5.ps1", "paper_run_30.ps1", "paper_daily_summary.ps1"))


def test_operational_scripts_stay_rooted_in_the_repository_and_use_venv_python():
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert "Split-Path -Parent $PSScriptRoot" in text
        assert "Set-Location -LiteralPath $repoRoot" in text
        assert "venv\\Scripts\\python.exe" in text


def test_operational_scripts_never_enable_live_or_submit_broker_orders():
    forbidden = ("ENABLE_LIVE_TRADING = True", "--live", "place_order", "submit_order", "Remove-Item -Recurse", "git reset")
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path.name


def test_canary_prints_only_safe_runtime_evidence_fields():
    text = (ROOT / "scripts" / "paper_canary.ps1").read_text(encoding="utf-8")
    assert 'Runtime evidence: $($_.event) at $($_.occurred_at)' in text
    assert "Write-Host $_.Line" not in text


def test_runtime_launchers_use_only_certified_automated_paper_and_expected_cycle_counts():
    expected = {"paper_canary.ps1": "--max-cycles 1", "paper_run_5.ps1": "--max-cycles 5", "paper_run_30.ps1": "--max-cycles 30"}
    for name, count in expected.items():
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "--automated-paper" in text
        assert "certified_runtime_launcher" in text
        assert count in text


def test_preflight_checks_apt_env_names_runtime_writes_and_paper_safety():
    text = (ROOT / "scripts" / "paper_preflight.ps1").read_text(encoding="utf-8")
    for token in ("test_apt1_automated_paper_runtime.py", "ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET", "paper_preflight_write_probe", 'BROKER = "PAPER"', "ENABLE_LIVE_TRADING = False"):
        assert token in text
