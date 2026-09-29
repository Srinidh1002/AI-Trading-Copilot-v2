"""F15-R2 M9 fix — index liveness must not recycle live positions.

Canary incident 2026-09-29:
  NIFTY + SENSEX opened legitimate PAPER positions at 11:01, P&L rose
  to +3.6% / +4.5%. Index workers only emit heartbeats at SESSION start
  and SLEEP end, never during active management. After 300 seconds, the
  R1 liveness watchdog classified the heartbeat as HEARTBEAT_STALE, and
  only the fact that we killed the supervisor manually prevented a
  recycle that would have abandoned both positions.

This file proves:
  * _check_worker_liveness returns False for NIFTY/SENSEX unconditionally
  * MCX liveness behavior unchanged (43s healthy, 900s stale)
  * _market_has_persisted_position handles index active_trades (list)
  * _market_has_persisted_position still handles MCX active_position (dict)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.paper_orchestration.automated_paper_supervisor_v2 import (
    AutomatedPaperSupervisorV2,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _sup(tmp_path):
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe="python",
        dry_run=True,
    )


def _spec_for(sup, market):
    return next(s for s in sup._enabled_specs() if s.name == market)


def _write_hb(tmp_path, market, *, age_seconds, stage="CHAIN"):
    d = tmp_path / "logs" / "supervisor" / "heartbeats"
    d.mkdir(parents=True, exist_ok=True)
    ts = (datetime.now(IST) - timedelta(seconds=age_seconds)).isoformat()
    (d / (market + ".json")).write_text(
        json.dumps({
            "schema_version": 1, "market": market, "pid": 1,
            "worker_generation": 1, "timestamp": ts,
            "cycle_number": 1, "stage": stage,
            "stage_started_at": ts, "last_cycle_completed_at": None,
            "has_active_position": False, "trade_id": None,
            "execution_mode": "PAPER",
        }),
        encoding="utf-8",
    )


# ---------- index liveness skip ----------

def test_nifty_stale_heartbeat_not_recycled(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    rt = sup.workers["NIFTY"]
    _write_hb(tmp_path, "NIFTY", age_seconds=3600.0, stage="SESSION")

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is False
    assert stop_calls == []


def test_sensex_stale_heartbeat_not_recycled(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "SENSEX")
    rt = sup.workers["SENSEX"]
    _write_hb(tmp_path, "SENSEX", age_seconds=7200.0, stage="SESSION")

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is False
    assert stop_calls == []


def test_nifty_very_stale_heartbeat_still_not_recycled(tmp_path, monkeypatch):
    """Even a 12-hour-old index heartbeat must not recycle."""
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    rt = sup.workers["NIFTY"]
    _write_hb(tmp_path, "NIFTY", age_seconds=12 * 3600.0, stage="SESSION")

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False
    assert stop_calls == []


# ---------- MCX behavior unchanged ----------

def test_mcx_43s_healthy_not_recycled(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=43.0, stage="CHAIN")
    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False
    assert stop_calls == []


def test_mcx_stale_flat_recycled(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")
    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is True
    assert stop_calls == ["NATGASMINI"]


# ---------- _market_has_persisted_position ----------

def test_index_active_trades_list_is_detected(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "nifty_experimental.json").write_text(json.dumps({
        "active_trades": [{"trade_id": "TRD_NIFTY_ABC", "status": "OPEN"}],
    }), encoding="utf-8")
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    assert sup._market_has_persisted_position(spec) is True


def test_index_empty_active_trades_is_flat(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "nifty_experimental.json").write_text(json.dumps({
        "active_trades": [],
    }), encoding="utf-8")
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    assert sup._market_has_persisted_position(spec) is False


def test_index_missing_state_is_flat(tmp_path):
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    assert sup._market_has_persisted_position(spec) is False


def test_sensex_active_trades_list_is_detected(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "sensex_experimental.json").write_text(json.dumps({
        "active_trades": [{"trade_id": "TRD_SENSEX_ABC", "status": "OPEN"}],
    }), encoding="utf-8")
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "SENSEX")
    assert sup._market_has_persisted_position(spec) is True


def test_mcx_active_position_dict_is_detected(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "mcx_goldm_experimental.json").write_text(json.dumps({
        "active_position": {"trade_id": "MCX_GOLDM_ABC", "entry_time": "x"},
    }), encoding="utf-8")
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    assert sup._market_has_persisted_position(spec) is True


def test_mcx_missing_active_position_is_flat(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "mcx_goldm_experimental.json").write_text(json.dumps({
        "active_position": None,
    }), encoding="utf-8")
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    assert sup._market_has_persisted_position(spec) is False
