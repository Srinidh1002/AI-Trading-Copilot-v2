"""Part 2 — canonical credential authority. No network, no live .env."""
from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.broker.fyers_auth_v2 import (
    FyersAuthError,
    load_canonical_credentials_v2,
)
from tools import preflight_and_start_five_market_paper as pf


def _write_env(tmp_path, **kv):
    p = tmp_path / ".env"
    lines = [f"{k}={v}" for k, v in kv.items()]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("FYERS_APP_ID", "FYERS_SECRET_ID", "FYERS_ACCESS_TOKEN",
              "FYERS_REFRESH_TOKEN", "FYERS_REDIRECT_URI", "FYERS_PIN"):
        monkeypatch.delenv(k, raising=False)


# ---------- canonical loader --------------------------------------------------

def test_canonical_loader_reads_file_values(tmp_path, clean_env):
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="CANONICAL_APP",
        FYERS_ACCESS_TOKEN="CANONICAL_TOKEN",
        FYERS_SECRET_ID="CANONICAL_SECRET",
        FYERS_REDIRECT_URI="https://canonical",
    )
    creds = load_canonical_credentials_v2(str(envp))
    assert creds.app_id == "CANONICAL_APP"
    assert creds.access_token == "CANONICAL_TOKEN"
    assert creds.secret_id == "CANONICAL_SECRET"
    assert creds.redirect_uri == "https://canonical"
    assert creds.source.startswith("canonical:")


def test_canonical_loader_beats_stale_parent_token(tmp_path, monkeypatch):
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="FRESH_APP",
        FYERS_ACCESS_TOKEN="FRESH_TOKEN",
    )
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "STALE_TOKEN")
    monkeypatch.setenv("FYERS_APP_ID", "STALE_APP")
    creds = load_canonical_credentials_v2(str(envp))
    assert creds.app_id == "FRESH_APP"
    assert creds.access_token == "FRESH_TOKEN"


def test_canonical_loader_does_not_mutate_os_environ(tmp_path, monkeypatch):
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="FRESH",
        FYERS_ACCESS_TOKEN="FRESH_TOKEN",
    )
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "PARENT_TOKEN")
    monkeypatch.setenv("FYERS_APP_ID", "PARENT_APP")
    before = dict(os.environ)
    load_canonical_credentials_v2(str(envp))
    after = dict(os.environ)
    assert before == after, "canonical loader must not mutate os.environ"


def test_canonical_loader_raises_when_app_id_missing(tmp_path, clean_env, monkeypatch):
    envp = _write_env(tmp_path, FYERS_ACCESS_TOKEN="T")
    monkeypatch.setenv("FYERS_APP_ID", "STALE_PARENT_APP")
    with pytest.raises(FyersAuthError, match="APP_ID"):
        load_canonical_credentials_v2(str(envp))


def test_canonical_loader_raises_when_token_missing(tmp_path, clean_env, monkeypatch):
    envp = _write_env(tmp_path, FYERS_APP_ID="A")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "STALE_PARENT_TOKEN")
    with pytest.raises(FyersAuthError, match="ACCESS_TOKEN"):
        load_canonical_credentials_v2(str(envp))


def test_canonical_loader_raises_on_empty_file(tmp_path, clean_env):
    p = tmp_path / "empty.env"
    p.write_text("", encoding="utf-8")
    with pytest.raises(FyersAuthError):
        load_canonical_credentials_v2(str(p))


# ---------- preflight integration --------------------------------------------

def test_preflight_check_env_file_uses_canonical(tmp_path, monkeypatch):
    """Parent has stale values; .env has fresh. preflight must report fresh."""
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="FRESH_APP",
        FYERS_ACCESS_TOKEN="FRESH_TOKEN",
    )
    monkeypatch.setenv("FYERS_APP_ID", "STALE_APP")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "STALE_TOKEN")

    captured = {}
    def _fake_assert(token):
        captured["token"] = token
    from services.broker import fyers_auth_v2 as auth
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", _fake_assert)

    ok, why, creds = pf.check_env_file(str(envp))
    assert ok is True, f"expected OK, got {why}"
    assert creds is not None
    assert creds.app_id == "FRESH_APP"
    assert creds.access_token == "FRESH_TOKEN"
    assert captured["token"] == "FRESH_TOKEN"


def test_preflight_check_env_file_reports_missing_canonical(tmp_path, monkeypatch):
    envp = _write_env(tmp_path, FYERS_ACCESS_TOKEN="T")  # no APP_ID
    monkeypatch.setenv("FYERS_APP_ID", "STALE_PARENT_APP")
    ok, why, creds = pf.check_env_file(str(envp))
    assert ok is False
    assert creds is None
    # Preflight surfaces the reason code, not the raw exception message.
    # Stale parent FYERS_APP_ID must not rescue a canonical env missing it.
    assert "AUTH_MISSING" in why


def test_preflight_check_env_file_no_fake_success_when_expired(tmp_path, monkeypatch):
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_ACCESS_TOKEN="TOKEN",
    )
    from services.broker import fyers_auth_v2 as auth
    def _fake_assert(token):
        raise FyersAuthError("AUTH_EXPIRED", "expired")
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", _fake_assert)
    ok, why, creds = pf.check_env_file(str(envp))
    assert ok is False
    assert "AUTH_EXPIRED" in why


def test_preflight_never_prints_token(tmp_path, monkeypatch):
    envp = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_ACCESS_TOKEN="SECRET_TOKEN_VALUE",
    )
    from services.broker import fyers_auth_v2 as auth
    monkeypatch.setattr(auth, "assert_fyers_token_current_v2", lambda t: None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        pf.check_env_file(str(envp))
    assert "SECRET_TOKEN_VALUE" not in buf.getvalue()
