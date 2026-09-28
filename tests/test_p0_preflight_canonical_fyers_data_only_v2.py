"""F15 Phase 2 — FYERS_DATA_ONLY canonical .env authority."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from tools import preflight_and_start_five_market_paper as pf  # noqa: E402


def _write_env(tmp_path, **kv):
    p = tmp_path / ".env"
    p.write_text("\n".join(f"{k}={v}" for k, v in kv.items()) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def clean(monkeypatch):
    for k in (
        "BROKER_SUBMISSION",
        "BROKER_SUBMISSION_ENABLED",
        "LIVE_EXECUTION",
        "LIVE_EXECUTION_ENABLED",
        "LIVE_EXECUTION_ELIGIBLE",
        "EXECUTION_MODE",
        "FYERS_DATA_ONLY",
    ):
        monkeypatch.delenv(k, raising=False)


# --- canonical .env is sole authority when env_file is given ---------------

def test_canonical_true_parent_missing_passes(tmp_path, clean):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="true")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is True, why


def test_canonical_missing_parent_true_is_hold(tmp_path, clean, monkeypatch):
    env = _write_env(tmp_path, SOME_OTHER_KEY="x")  # no FYERS_DATA_ONLY
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is False
    assert "missing" in why
    assert "canonical .env" in why


def test_canonical_true_parent_false_passes(tmp_path, clean, monkeypatch):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="true")
    monkeypatch.setenv("FYERS_DATA_ONLY", "false")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is True, why


def test_canonical_false_parent_true_is_hold(tmp_path, clean, monkeypatch):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="false")
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is False
    assert "FYERS_DATA_ONLY" in why


def test_canonical_empty_value_is_hold(tmp_path, clean):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is False


def test_canonical_invalid_boolean_is_hold(tmp_path, clean):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="banana")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is False
    assert "not a valid boolean" in why


# --- legacy path (env_file=None) still works for direct unit calls --------

def test_legacy_process_env_true_passes(clean, monkeypatch):
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags(None)
    assert ok is True


def test_legacy_process_env_missing_is_hold(clean):
    ok, why = pf.check_paper_flags(None)
    assert ok is False
    assert "missing" in why


# --- safety flags still fail closed regardless of file --------------------

def test_unsafe_flag_in_parent_holds_even_with_valid_file(tmp_path, clean, monkeypatch):
    env = _write_env(tmp_path, FYERS_DATA_ONLY="true")
    monkeypatch.setenv("LIVE_EXECUTION", "true")
    ok, why = pf.check_paper_flags(str(env))
    assert ok is False
    assert "unsafe flags" in why


# --- integration: --dry-run reads FYERS_DATA_ONLY from repo .env ---------

def test_main_dry_run_uses_repo_env(tmp_path, clean, monkeypatch):
    """The repo .env supplies FYERS_DATA_ONLY; parent env is silent."""
    (tmp_path / "run_nifty.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "run_sensex.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "FYERS_APP_ID=FAKE\n"
        "FYERS_ACCESS_TOKEN=FAKE.TOKEN.SIG\n"
        "FYERS_DATA_ONLY=true\n",
        encoding="utf-8",
    )

    # Stub the auth + downstream checks so we exercise only the flow
    class _Creds:
        app_id = "FAKE"
        access_token = "FAKE.TOKEN.SIG"
    from services.broker import fyers_auth_v2 as auth
    monkeypatch.setattr(auth, "load_canonical_credentials_v2", lambda _p: _Creds())
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", lambda _t: None)

    monkeypatch.setattr(
        pf, "check_locks",
        lambda markets: ({"supervisor": True, **{m: True for m in markets}}, ""),
    )
    monkeypatch.setattr(pf, "check_rate_limiter", lambda: (True, "ok"))
    monkeypatch.setattr(
        pf, "check_cert_authority",
        lambda markets: {m: (True, "counter=0") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_state_authority",
        lambda markets, repo_root: {m: (True, "STATE_OK") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_calendar",
        lambda markets, now: {m: (True, "OPEN") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {m: (True, "calibrated") for m in markets},
    )
    monkeypatch.setattr(
        pf, "check_provider_health",
        lambda creds, markets: {m: (True, "ok") for m in markets},
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = pf.main(["--repo-root", str(tmp_path), "--dry-run"])
    out = buf.getvalue()
    assert "[PAPER" in out and "OK" in out, out
    assert "PREFLIGHT=NOMINAL" in out, out
    assert rc == 0, out
