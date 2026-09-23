"""Wave 3b — cooperative stop protocol (worker side). No real workers."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import cooperative_stop_v2 as cs  # noqa: E402


@pytest.fixture
def env_files(monkeypatch, tmp_path):
    req = tmp_path / "NIFTY.request"
    ack = tmp_path / "NIFTY.ack"
    monkeypatch.setenv("PAPER_STOP_REQUEST_FILE", str(req))
    monkeypatch.setenv("PAPER_STOP_ACK_FILE", str(ack))
    yield req, ack
    monkeypatch.delenv("PAPER_STOP_REQUEST_FILE", raising=False)
    monkeypatch.delenv("PAPER_STOP_ACK_FILE", raising=False)


def test_stop_not_requested_when_file_absent(env_files):
    req, _ = env_files
    assert req.exists() is False
    assert cs.stop_requested() is False


def test_stop_requested_when_file_present(env_files):
    req, _ = env_files
    req.parent.mkdir(parents=True, exist_ok=True)
    req.write_text("STOP_NEW_ENTRIES", encoding="utf-8")
    assert cs.stop_requested() is True


def test_acknowledge_writes_expected_payload(env_files):
    _, ack = env_files
    cs.acknowledge(reason="TEST_REASON", extra={"market": "NIFTY"})
    assert ack.exists()
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["reason"] == "TEST_REASON"
    assert data["market"] == "NIFTY"
    assert data["pid"] == os.getpid()
    assert "acked_at_utc" in data


def test_acknowledge_is_idempotent(env_files):
    _, ack = env_files
    cs.acknowledge(reason="FIRST")
    cs.acknowledge(reason="SECOND")
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["reason"] == "SECOND"  # last write wins


def test_no_env_vars_is_noop(monkeypatch):
    monkeypatch.delenv("PAPER_STOP_REQUEST_FILE", raising=False)
    monkeypatch.delenv("PAPER_STOP_ACK_FILE", raising=False)
    assert cs.stop_requested() is False
    cs.acknowledge(reason="NOOP")  # must not raise


def test_acknowledge_never_leaks_secrets(env_files):
    _, ack = env_files
    cs.acknowledge(reason="TEST", extra={"market": "NIFTY"})
    raw = ack.read_text(encoding="utf-8").lower()
    assert "token" not in raw
    assert "secret" not in raw
    assert "password" not in raw
    assert "auth" not in raw


# ---- integration: run_nifty.py and run_sensex.py contain the checks ----

def test_run_nifty_contains_cooperative_stop_call():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    assert "cooperative_stop_v2 import" in src
    assert "_coop_stop_requested()" in src
    assert "COOPERATIVE_STOP_FLAT" in src


def test_run_sensex_contains_cooperative_stop_call():
    src = (REPO / "run_sensex.py").read_text(encoding="utf-8")
    assert "cooperative_stop_v2 import" in src
    assert "_coop_stop_requested()" in src
    assert "COOPERATIVE_STOP_FLAT" in src


def test_mcx_paper_bot_contains_cooperative_stop_call():
    src = (REPO / "src" / "mcx" / "mcx_paper_bot.py").read_text(encoding="utf-8")
    assert "cooperative_stop_v2 import" in src
    assert "_coop_stop_requested()" in src
    assert "COOPERATIVE_STOP_FLAT" in src
