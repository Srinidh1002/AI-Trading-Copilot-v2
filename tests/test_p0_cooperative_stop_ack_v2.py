"""Part 9a — enriched cooperative stop protocol. Worker-side ACK shapes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import cooperative_stop_v2 as cs


@pytest.fixture
def env_files(monkeypatch, tmp_path):
    req = tmp_path / "NIFTY.request"
    ack = tmp_path / "NIFTY.ack"
    monkeypatch.setenv("PAPER_STOP_REQUEST_FILE", str(req))
    monkeypatch.setenv("PAPER_STOP_ACK_FILE", str(ack))
    monkeypatch.setenv("PAPER_MARKET_NAME", "NIFTY")
    yield req, ack
    for k in ("PAPER_STOP_REQUEST_FILE", "PAPER_STOP_ACK_FILE", "PAPER_MARKET_NAME"):
        monkeypatch.delenv(k, raising=False)


def test_flat_ack_shape(env_files):
    _, ack = env_files
    cs.acknowledge(reason="FLAT_ACK_EXIT", status=cs.STATUS_FLAT_SAFE_TO_EXIT,
                   has_active_position=False)
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["status"] == "FLAT_SAFE_TO_EXIT"
    assert data["has_active_position"] is False
    assert data["market"] == "NIFTY"
    assert data["pid"] == os.getpid()
    assert "acked_at_utc" in data
    assert "reason" in data


def test_position_mgmt_ack_shape(env_files):
    _, ack = env_files
    cs.acknowledge(reason="POSITION_MANAGEMENT_ACTIVE",
                   status=cs.STATUS_POSITION_MANAGEMENT_ACTIVE,
                   has_active_position=True,
                   trade_id="TRD_20260924_100000")
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["status"] == "POSITION_MANAGEMENT_ACTIVE"
    assert data["has_active_position"] is True
    assert data["trade_id"] == "TRD_20260924_100000"


def test_terminal_reconciled_status(env_files):
    _, ack = env_files
    cs.acknowledge(reason="TERMINAL", status=cs.STATUS_TERMINAL_RECONCILED,
                   has_active_position=False)
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["status"] == "TERMINAL_RECONCILED"


def test_unknown_status_downgrades_to_state_hold(env_files):
    _, ack = env_files
    cs.acknowledge(status="BOGUS_STATUS", has_active_position=False)
    data = json.loads(ack.read_text(encoding="utf-8"))
    assert data["status"] == "STATE_HOLD"


def test_no_token_or_secret_fields_written(env_files):
    _, ack = env_files
    cs.acknowledge(reason="TEST", extra={"FYERS_ACCESS_TOKEN": "SHOULD_NOT_APPEAR",
                                          "user_secret": "nope",
                                          "user_pin": "1234",
                                          "safe_field": "yes"})
    data = json.loads(ack.read_text(encoding="utf-8"))
    payload_str = json.dumps(data).lower()
    assert "should_not_appear" not in payload_str
    assert "nope" not in payload_str
    assert "1234" not in payload_str
    assert data.get("safe_field") == "yes"


def test_read_ack_returns_dict(env_files):
    _, ack = env_files
    assert cs.read_ack() is None
    cs.acknowledge(reason="TEST", status=cs.STATUS_FLAT_SAFE_TO_EXIT)
    r = cs.read_ack()
    assert isinstance(r, dict)
    assert r["status"] == "FLAT_SAFE_TO_EXIT"


def test_read_ack_tolerates_corrupt(env_files):
    _, ack = env_files
    ack.parent.mkdir(parents=True, exist_ok=True)
    ack.write_text("{not json", encoding="utf-8")
    assert cs.read_ack() is None


# --- integration sentinels: worker files carry the enriched ACK shapes -----

def test_run_nifty_uses_status_constant():
    src = (REPO / "run_nifty.py").read_text(encoding="utf-8")
    assert "STATUS_FLAT_SAFE_TO_EXIT" in src
    assert "_COOP_FLAT" in src
    assert "has_active_position=False" in src or "has_active_position=True" in src


def test_run_sensex_uses_status_constant():
    src = (REPO / "run_sensex.py").read_text(encoding="utf-8")
    assert "STATUS_FLAT_SAFE_TO_EXIT" in src
    assert "_COOP_FLAT" in src


def test_mcx_uses_status_constant():
    src = (REPO / "src" / "mcx" / "mcx_paper_bot.py").read_text(encoding="utf-8")
    assert "STATUS_FLAT_SAFE_TO_EXIT" in src
    assert "STATUS_POSITION_MANAGEMENT_ACTIVE" in src
