"""Phase 1 — canonical .env authority for FYERS OAuth input loading."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from services.broker.fyers_auth_v2 import (  # noqa: E402
    FyersAuthError,
    load_fyers_oauth_inputs_v2,
)


def _write_env(tmp_path, **kv):
    p = tmp_path / ".env"
    lines = [f"{k}={v}" for k, v in kv.items()]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def clean_env(monkeypatch):
    for k in (
        "FYERS_APP_ID",
        "FYERS_SECRET_ID",
        "FYERS_REDIRECT_URI",
        "FYERS_ACCESS_TOKEN",
        "FYERS_REFRESH_TOKEN",
        "FYERS_PIN",
    ):
        monkeypatch.delenv(k, raising=False)


# --- canonical file wins over parent --------------------------------------

def test_env_file_wins_over_stale_parent_app_id(tmp_path, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="FRESH_APP",
        FYERS_SECRET_ID="FRESH_SECRET",
        FYERS_REDIRECT_URI="https://fresh/cb",
        FYERS_ACCESS_TOKEN="FRESH_TOKEN",
    )
    monkeypatch.setenv("FYERS_APP_ID", "STALE_APP")
    monkeypatch.setenv("FYERS_SECRET_ID", "STALE_SECRET")
    monkeypatch.setenv("FYERS_REDIRECT_URI", "https://stale/cb")
    inputs = load_fyers_oauth_inputs_v2(env_file=str(env))
    assert inputs.app_id == "FRESH_APP"
    assert inputs.secret_id == "FRESH_SECRET"
    assert inputs.redirect_uri == "https://fresh/cb"
    assert inputs.access_token == "FRESH_TOKEN"


def test_env_file_wins_over_stale_parent_token(tmp_path, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="APP",
        FYERS_SECRET_ID="SECRET",
        FYERS_REDIRECT_URI="https://cb",
        FYERS_ACCESS_TOKEN="FRESH_TOKEN",
    )
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "STALE_TOKEN")
    inputs = load_fyers_oauth_inputs_v2(env_file=str(env))
    assert inputs.access_token == "FRESH_TOKEN"


def test_empty_parent_values_do_not_cause_missing(tmp_path, monkeypatch):
    """Previously this was the reported failure mode."""
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="FILE_APP",
        FYERS_SECRET_ID="FILE_SECRET",
        FYERS_REDIRECT_URI="https://file/cb",
        FYERS_ACCESS_TOKEN="FILE_TOKEN",
    )
    monkeypatch.setenv("FYERS_APP_ID", "")
    monkeypatch.setenv("FYERS_SECRET_ID", "")
    monkeypatch.setenv("FYERS_REDIRECT_URI", "")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "")
    inputs = load_fyers_oauth_inputs_v2(env_file=str(env))
    assert inputs.app_id == "FILE_APP"
    assert inputs.secret_id == "FILE_SECRET"
    assert inputs.redirect_uri == "https://file/cb"
    assert inputs.access_token == "FILE_TOKEN"


def test_does_not_mutate_os_environ(tmp_path, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="APP",
        FYERS_SECRET_ID="SECRET",
        FYERS_REDIRECT_URI="https://cb",
        FYERS_ACCESS_TOKEN="TOKEN",
    )
    monkeypatch.setenv("FYERS_APP_ID", "PARENT")
    before = dict(__import__("os").environ)
    load_fyers_oauth_inputs_v2(env_file=str(env))
    after = dict(__import__("os").environ)
    assert before == after


# --- required fields fail closed -------------------------------------------

def test_missing_app_id_raises(tmp_path, clean_env, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_SECRET_ID="S",
        FYERS_REDIRECT_URI="https://cb",
    )
    monkeypatch.setenv("FYERS_APP_ID", "STALE")
    with pytest.raises(FyersAuthError) as exc_info:
        load_fyers_oauth_inputs_v2(env_file=str(env))
    assert "APP_ID" in str(exc_info.value)


def test_missing_secret_id_raises(tmp_path, clean_env, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_REDIRECT_URI="https://cb",
    )
    monkeypatch.setenv("FYERS_SECRET_ID", "STALE")
    with pytest.raises(FyersAuthError) as exc_info:
        load_fyers_oauth_inputs_v2(env_file=str(env))
    assert "SECRET_ID" in str(exc_info.value)


def test_missing_redirect_uri_raises(tmp_path, clean_env, monkeypatch):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_SECRET_ID="S",
    )
    monkeypatch.setenv("FYERS_REDIRECT_URI", "https://stale")
    with pytest.raises(FyersAuthError) as exc_info:
        load_fyers_oauth_inputs_v2(env_file=str(env))
    assert "REDIRECT_URI" in str(exc_info.value)


# --- access token is optional ----------------------------------------------

def test_missing_access_token_still_permits_oauth(tmp_path, clean_env):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_SECRET_ID="S",
        FYERS_REDIRECT_URI="https://cb",
    )
    inputs = load_fyers_oauth_inputs_v2(env_file=str(env))
    assert inputs.app_id == "A"
    assert inputs.access_token is None


# --- source field ---------------------------------------------------------

def test_source_reflects_canonical_file(tmp_path, clean_env):
    env = _write_env(
        tmp_path,
        FYERS_APP_ID="A",
        FYERS_SECRET_ID="S",
        FYERS_REDIRECT_URI="https://cb",
    )
    inputs = load_fyers_oauth_inputs_v2(env_file=str(env))
    assert inputs.source.startswith("canonical:")


# --- legacy path (env_file=None) preserved --------------------------------

def test_legacy_path_reads_process_env_when_no_file(clean_env, monkeypatch):
    monkeypatch.setenv("FYERS_APP_ID", "FROM_PARENT")
    monkeypatch.setenv("FYERS_SECRET_ID", "P_SECRET")
    monkeypatch.setenv("FYERS_REDIRECT_URI", "https://parent/cb")
    inputs = load_fyers_oauth_inputs_v2(env_file=None)
    assert inputs.app_id == "FROM_PARENT"
    assert inputs.source == "process_env_or_default_env"
