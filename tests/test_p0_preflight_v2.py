"""Wave 4 — canonical preflight launcher tests. All synthetic, no live state."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import preflight_and_start_five_market_paper as pf  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path):
    """A minimal synthetic repo with run_nifty.py and .env."""
    (tmp_path / "run_nifty.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "run_sensex.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "FYERS_APP_ID=FAKE\nFYERS_ACCESS_TOKEN=FAKE.TOKEN.SIG\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def stub_creds(monkeypatch):
    """Stub the auth path so preflight does not hit .env parsing."""
    creds = SimpleNamespace(app_id="FAKE", access_token="FAKE.TOKEN.SIG")

    def fake_load(env_file):
        return creds

    def fake_assert(token):
        return None

    from services.broker import fyers_auth_v2 as auth
    monkeypatch.setattr(auth, "load_fyers_credentials_v2", fake_load)
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", fake_assert)
    return creds


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure no unsafe flags leak in from the environment."""
    for k in ("BROKER_SUBMISSION", "BROKER_SUBMISSION_ENABLED",
              "LIVE_EXECUTION", "LIVE_EXECUTION_ENABLED",
              "LIVE_EXECUTION_ELIGIBLE"):
        monkeypatch.delenv(k, raising=False)


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = pf.main(argv)
    return rc, buf.getvalue()


# ---------- infrastructure failures --------------------------------------

def test_infra_fail_missing_repo(tmp_path, monkeypatch):
    rc, out = _run(["--repo-root", str(tmp_path / "does_not_exist"),
                    "--dry-run"])
    assert rc == 1
    assert "PREFLIGHT=HOLD" in out


def test_infra_fail_missing_env_file(fake_repo, stub_creds, clean_env):
    (fake_repo / ".env").unlink()
    # Remove the stub so real check runs
    import services.broker.fyers_auth_v2 as auth
    # Not stubbed here — make load raise
    orig = auth.load_fyers_credentials_v2
    def fake_load(env_file):
        raise RuntimeError("no file")
    auth.load_fyers_credentials_v2 = fake_load
    try:
        rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    finally:
        auth.load_fyers_credentials_v2 = orig
    assert rc == 1
    assert "PREFLIGHT=HOLD" in out
    assert "AUTH" in out and "FAIL" in out


def test_infra_fail_unsafe_flag(fake_repo, stub_creds, monkeypatch):
    monkeypatch.setenv("LIVE_EXECUTION", "true")
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 1
    assert "PREFLIGHT=HOLD" in out
    assert "unsafe flags" in out


def test_bad_markets_argument_exits_2(fake_repo, stub_creds, clean_env):
    rc, _ = _run(["--repo-root", str(fake_repo), "--dry-run",
                  "--markets", "BOGUS"])
    assert rc == 2


# ---------- success paths -------------------------------------------------

def _patch_all_ok(monkeypatch):
    """Stub every per-market check to OK, only NIFTY/SENSEX n/a calib."""
    from services.paper_orchestration.certification_halt_v2 import MarketState
    monkeypatch.setattr(
        pf, "check_cert_authority",
        lambda markets: {m: (True, "counter=0") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_state_authority",
        lambda markets: {m: (True, "state ok") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_calendar",
        lambda markets, now: {m: (True, "OPEN") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {m: (True, "n/a") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_provider_health",
        lambda creds, markets: {m: (True, "ok") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_locks",
        lambda markets: ({"supervisor": True, **{m: True for m in markets}}, ""),
    )
    monkeypatch.setattr(pf, "check_rate_limiter", lambda: (True, "ok"))


def test_nominal_all_five_ready(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0
    assert "PREFLIGHT=NOMINAL" in out
    assert "READY_MARKETS=NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI" in out
    assert "HELD_MARKETS=-" in out
    assert "SUPERVISOR_STARTED=False" in out


def test_partial_two_ready(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    # Override: MCX markets held on calibration
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {
            m: ((True, "n/a") if m in ("NIFTY", "SENSEX")
                else (False, "CALIBRATION_MISSING:X"))
            for m in markets
        },
    )
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0
    assert "PREFLIGHT=PARTIAL" in out
    assert "READY_MARKETS=NIFTY,SENSEX" in out
    assert "CRUDEOILM" in out.split("HELD_MARKETS=")[1].split("\n")[0]
    assert "SUPERVISOR_STARTED=False" in out


def test_hold_zero_ready(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {m: (False, "CALIBRATION_MISSING:X") for m in markets},
    )
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0
    assert "PREFLIGHT=HOLD" in out
    assert "SUPERVISOR_STARTED=False" in out


def test_dry_run_does_not_launch(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    called = {"exec": 0}

    import subprocess as sp
    real_call = sp.call
    def _fake_call(*a, **k):
        called["exec"] += 1
        return 0
    monkeypatch.setattr(pf.subprocess, "call", _fake_call)

    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0
    assert called["exec"] == 0
    assert "DRY_RUN: would exec:" in out


def test_launch_path_invokes_supervisor_with_ready_markets(
    fake_repo, stub_creds, clean_env, monkeypatch
):
    _patch_all_ok(monkeypatch)
    captured = {}
    def _fake_call(cmd, **kw):
        captured["cmd"] = cmd
        return 0
    monkeypatch.setattr(pf.subprocess, "call", _fake_call)

    rc, _ = _run(["--repo-root", str(fake_repo)])  # NOT dry-run
    assert rc == 0
    assert "automated_paper_supervisor_v2" in " ".join(captured["cmd"])
    assert "--markets" in captured["cmd"]
    idx = captured["cmd"].index("--markets")
    assert captured["cmd"][idx + 1] == "NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI"


def test_markets_filter_restricts_ready_set(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    captured = {}
    def _fake_call(cmd, **kw):
        captured["cmd"] = cmd
        return 0
    monkeypatch.setattr(pf.subprocess, "call", _fake_call)
    rc, _ = _run(["--repo-root", str(fake_repo), "--markets", "nifty,sensex"])
    assert rc == 0
    idx = captured["cmd"].index("--markets")
    assert captured["cmd"][idx + 1] == "NIFTY,SENSEX"


def test_summary_format_lines_present(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ok(monkeypatch)
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0
    for needle in (
        "PREFLIGHT=",
        "READY_MARKETS=",
        "HELD_MARKETS=",
        "SUPERVISOR_STARTED=",
    ):
        assert needle in out, f"missing summary line: {needle}"


def test_no_secret_printed(fake_repo, stub_creds, clean_env, monkeypatch):
    """The token value and secret field names must never appear in stdout."""
    _patch_all_ok(monkeypatch)
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    lowered = out.lower()
    # The token value itself
    assert "fake.token.sig" not in lowered
    # Env field names that would only appear if we dumped credentials
    assert "fyers_access_token" not in lowered
    assert "fyers_secret_id" not in lowered
    assert "access_token=" not in lowered
