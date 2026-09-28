"""Phase 6 — worker liveness classifier tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.paper_orchestration import worker_liveness_v2 as lv

IST = timezone(timedelta(hours=5, minutes=30))


def _write(tmp_path, market, payload):
    (tmp_path / (market + ".json")).write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _beat_payload(market, *, ts=None, stage="CHAIN"):
    return {
        "schema_version": 1,
        "market": market,
        "pid": 1234,
        "worker_generation": 1,
        "timestamp": ts or datetime.now(IST).isoformat(timespec="seconds"),
        "cycle_number": 1,
        "stage": stage,
        "stage_started_at": ts or datetime.now(IST).isoformat(timespec="seconds"),
        "last_cycle_completed_at": None,
        "has_active_position": False,
        "trade_id": None,
        "execution_mode": "PAPER",
    }


def test_no_heartbeat_file_returns_no_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    cls, hb, age = lv.classify("NATGASMINI", datetime.now(IST))
    assert cls == "NO_HEARTBEAT"
    assert hb == {}
    assert age is None


def test_fresh_heartbeat_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    now = datetime.now(IST)
    _write(tmp_path, "GOLDM", _beat_payload("GOLDM", ts=now.isoformat(timespec="seconds")))
    cls, hb, age = lv.classify("GOLDM", now)
    assert cls == "HEARTBEAT_OK"
    assert age is not None
    assert age < 5.0


def test_stale_heartbeat_detected(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    now = datetime.now(IST)
    old = now - timedelta(seconds=600)
    _write(tmp_path, "CRUDEOILM", _beat_payload("CRUDEOILM", ts=old.isoformat(timespec="seconds")))
    cls, hb, age = lv.classify("CRUDEOILM", now)
    assert cls == "HEARTBEAT_STALE"
    assert 590 <= age <= 610


def test_exactly_at_threshold_is_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    now = datetime.now(IST)
    at = now - timedelta(seconds=lv.HEARTBEAT_MAX_AGE_SECONDS)
    # Full-precision isoformat — timespec="seconds" would truncate
    # microseconds and push the observed age just past the threshold.
    _write(tmp_path, "NATGASMINI", _beat_payload("NATGASMINI", ts=at.isoformat()))
    cls, _, age = lv.classify("NATGASMINI", now)
    assert cls == "HEARTBEAT_OK"
    assert age <= lv.HEARTBEAT_MAX_AGE_SECONDS


def test_malformed_json_returns_no_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    (tmp_path / "GOLDM.json").write_text("{not json", encoding="utf-8")
    cls, hb, age = lv.classify("GOLDM", datetime.now(IST))
    assert cls == "NO_HEARTBEAT"
    assert hb == {}


def test_naive_timestamp_treated_as_ist(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    now = datetime.now(IST)
    naive = now.replace(tzinfo=None).isoformat(timespec="seconds")
    _write(tmp_path, "NATGASMINI", _beat_payload("NATGASMINI", ts=naive))
    cls, _, age = lv.classify("NATGASMINI", now)
    assert cls == "HEARTBEAT_OK"
    assert age is not None and age < 5.0


def test_reader_uses_paper_heartbeat_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    now = datetime.now(IST)
    _write(tmp_path, "GOLDM", _beat_payload("GOLDM", ts=now.isoformat(timespec="seconds")))
    assert lv.heartbeat_dir() == tmp_path
    assert lv.read_heartbeat("GOLDM") is not None
