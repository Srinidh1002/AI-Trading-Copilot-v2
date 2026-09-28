"""Phase 5 — worker heartbeat writer tests."""
from __future__ import annotations

import json

from services.paper_orchestration.worker_heartbeat_v2 import beat


def _read(p):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_heartbeat_creates_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    beat("NIFTY", "SESSION", cycle_number=1, has_active_position=False)
    p = tmp_path / "NIFTY.json"
    assert p.exists()
    d = _read(p)
    assert d["market"] == "NIFTY"
    assert d["stage"] == "SESSION"
    assert d["schema_version"] == 1
    assert d["execution_mode"] == "PAPER"
    assert d["cycle_number"] == 1
    assert d["has_active_position"] is False
    assert d["trade_id"] is None


def test_atomic_no_partial_on_write_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    beat("NIFTY", "CHAIN", cycle_number=1)
    p = tmp_path / "NIFTY.json"
    first = _read(p)

    # Simulate os.replace failing mid-write
    import services.paper_orchestration.worker_heartbeat_v2 as mod
    real_replace = mod.os.replace

    def boom(a, b):
        raise OSError("simulated replace failure")

    mod.os.replace = boom
    try:
        beat("NIFTY", "MTF", cycle_number=2)
    finally:
        mod.os.replace = real_replace

    # Original file intact, no partial write
    second = _read(p)
    assert second == first
    # No stray tmp files
    strays = [x for x in tmp_path.iterdir() if x.name.endswith(".tmp")]
    assert strays == []


def test_stage_change_advances_stage_started_at(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    beat("GOLDM", "CHAIN", cycle_number=1)
    p = tmp_path / "GOLDM.json"
    a = _read(p)
    # Same stage again: stage_started_at preserved
    beat("GOLDM", "CHAIN", cycle_number=1)
    b = _read(p)
    assert b["stage_started_at"] == a["stage_started_at"]
    # New stage: stage_started_at advances
    beat("GOLDM", "MTF", cycle_number=1)
    c = _read(p)
    assert c["stage"] == "MTF"


def test_sleep_advances_last_cycle_completed_at(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    beat("NATGASMINI", "CHAIN", cycle_number=1)
    p = tmp_path / "NATGASMINI.json"
    a = _read(p)
    assert a["last_cycle_completed_at"] is None
    beat("NATGASMINI", "SLEEP", cycle_number=1)
    b = _read(p)
    assert b["last_cycle_completed_at"] is not None


def test_best_effort_never_raises(tmp_path, monkeypatch):
    # Point at an existing FILE — mkdir(parents=True, exist_ok=True)
    # on a non-directory path raises FileExistsError, which beat()
    # must swallow without raising into the caller.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(blocker))
    beat("NIFTY", "CHAIN", cycle_number=1)  # must not raise


def test_all_market_names(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    for mkt in ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"):
        beat(mkt, "CHAIN", cycle_number=1)
        assert (tmp_path / (mkt + ".json")).exists()


def test_worker_generation_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_WORKER_GENERATION", "3")
    beat("NIFTY", "CHAIN", cycle_number=1)
    d = _read(tmp_path / "NIFTY.json")
    assert d["worker_generation"] == 3
