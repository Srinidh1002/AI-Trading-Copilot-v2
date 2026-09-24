"""Parts 11+12 — PAPER-only proof and preflight exit-code contract."""
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

from tools import preflight_and_start_five_market_paper as pf


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "run_nifty.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "run_sensex.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "FYERS_APP_ID=FAKE\nFYERS_ACCESS_TOKEN=FAKE.TOKEN.SIG\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def stub_creds(monkeypatch):
    creds = SimpleNamespace(app_id="FAKE", access_token="FAKE.TOKEN.SIG")
    from services.broker import fyers_auth_v2 as auth
    monkeypatch.setattr(auth, "load_fyers_credentials_v2", lambda env_file: creds)
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", lambda t: None)
    return creds


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("BROKER_SUBMISSION", "BROKER_SUBMISSION_ENABLED",
              "LIVE_EXECUTION", "LIVE_EXECUTION_ENABLED",
              "LIVE_EXECUTION_ELIGIBLE", "EXECUTION_MODE", "FYERS_DATA_ONLY"):
        monkeypatch.delenv(k, raising=False)
    # R2-4: preflight requires FYERS_DATA_ONLY=true explicitly.
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = pf.main(argv)
    return rc, buf.getvalue()


def _patch_all_ready(monkeypatch):
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
    monkeypatch.setattr(
        pf, "check_locks",
        lambda markets: ({"supervisor": True, **{m: True for m in markets}}, ""),
    )
    monkeypatch.setattr(pf, "check_rate_limiter", lambda: (True, "ok"))


# ---------- Part 11: paper flag expansion ---------------------------------

def test_execution_mode_must_be_paper(fake_repo, stub_creds, monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "LIVE")
    ok, why = pf.check_paper_flags()
    assert ok is False
    assert "EXECUTION_MODE" in why


def test_execution_mode_paper_passes(fake_repo, stub_creds, monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "PAPER")
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags()
    assert ok is True, why


def test_fyers_data_only_false_fails(monkeypatch):
    monkeypatch.setenv("FYERS_DATA_ONLY", "false")
    ok, why = pf.check_paper_flags()
    assert ok is False
    assert "DATA_ONLY" in why


def test_fyers_data_only_true_passes(monkeypatch):
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags()
    assert ok is True


# ---------- Part 12: exit code contract -----------------------------------

def test_nominal_all_five_returns_0(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ready(monkeypatch)
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 0, out
    assert "PREFLIGHT=NOMINAL" in out


def test_hold_zero_markets_returns_10(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ready(monkeypatch)
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {m: (False, "CALIBRATION_MISSING:X") for m in markets},
    )
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 10, out
    assert "PREFLIGHT=HOLD" in out
    assert "EXIT_CODE=10" in out


def test_partial_default_returns_11(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ready(monkeypatch)
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {
            m: ((True, "n/a") if m in ("NIFTY", "SENSEX")
                else (False, "CALIBRATION_MISSING:X"))
            for m in markets
        },
    )
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run"])
    assert rc == 11, out
    assert "PREFLIGHT=PARTIAL" in out
    assert "EXIT_CODE=11" in out


def test_partial_allow_partial_returns_0(fake_repo, stub_creds, clean_env, monkeypatch):
    _patch_all_ready(monkeypatch)
    monkeypatch.setattr(
        pf, "check_calibration",
        lambda markets: {
            m: ((True, "n/a") if m in ("NIFTY", "SENSEX")
                else (False, "CALIBRATION_MISSING:X"))
            for m in markets
        },
    )
    rc, out = _run(["--repo-root", str(fake_repo), "--dry-run", "--allow-partial"])
    assert rc == 0, out


def test_bad_markets_returns_2(fake_repo, stub_creds, clean_env):
    rc, _ = _run(["--repo-root", str(fake_repo), "--dry-run", "--markets", "BOGUS"])
    assert rc == 2


def test_missing_repo_returns_1(tmp_path, stub_creds, clean_env):
    rc, out = _run(["--repo-root", str(tmp_path / "nope"), "--dry-run"])
    assert rc == 1
    assert "PREFLIGHT=HOLD" in out


def test_fyers_data_only_missing_is_hold(monkeypatch):
    monkeypatch.delenv("FYERS_DATA_ONLY", raising=False)
    for k in ("BROKER_SUBMISSION", "BROKER_SUBMISSION_ENABLED",
              "LIVE_EXECUTION", "LIVE_EXECUTION_ENABLED",
              "LIVE_EXECUTION_ELIGIBLE", "EXECUTION_MODE"):
        monkeypatch.delenv(k, raising=False)
    ok, why = pf.check_paper_flags()
    assert ok is False
    assert "FYERS_DATA_ONLY" in why and "missing" in why


def test_fyers_data_only_false_is_hold(monkeypatch):
    monkeypatch.setenv("FYERS_DATA_ONLY", "false")
    ok, why = pf.check_paper_flags()
    assert ok is False
    assert "FYERS_DATA_ONLY" in why


def test_fyers_data_only_true_explicit_passes(monkeypatch):
    for k in ("BROKER_SUBMISSION", "BROKER_SUBMISSION_ENABLED",
              "LIVE_EXECUTION", "LIVE_EXECUTION_ENABLED",
              "LIVE_EXECUTION_ELIGIBLE", "EXECUTION_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("FYERS_DATA_ONLY", "true")
    ok, why = pf.check_paper_flags()
    assert ok is True, why
