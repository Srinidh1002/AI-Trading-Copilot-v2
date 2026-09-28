"""F15-R2 Phase R2-15 — watchdog recovery reconfirmation.

Complements tests/test_f15r1_supervisor_liveness_v2.py. Guards against
the failure mode the mission doc explicitly forbids: lowering the
heartbeat threshold into aggressive 5-10 second territory that would
recycle healthy workers on a slow-but-valid provider call.

Asserts:
  * HEARTBEAT_MAX_AGE_SECONDS stays conservative (> 120 s)
  * 43-second CHAIN call is classified healthy (NATGAS probe duration)
  * slow-but-within-budget stage remains healthy
  * genuinely stale heartbeat classified stale
  * flat-stale path calls _stop_worker exactly once and returns True
  * active-position-stale path sets recovery_required and returns True
  * healthy path does NOT stop worker and returns False
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.paper_orchestration import worker_liveness_v2 as lv
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


def _write_state(tmp_path, market, active=None):
    sd = tmp_path / "data" / "paper_trades"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"mcx_{market.lower()}_experimental.json").write_text(
        json.dumps({"active_position": active}), encoding="utf-8"
    )


# -------- threshold discipline --------

def test_threshold_is_not_aggressive():
    """Mission doc forbids 5-10 s aggressive thresholds."""
    assert lv.HEARTBEAT_MAX_AGE_SECONDS >= 120.0
    assert lv.HEARTBEAT_MAX_AGE_SECONDS <= 900.0


def test_43_second_chain_call_is_healthy(tmp_path, monkeypatch):
    """Live NATGAS probe measured the same chain call at ~43 s."""
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    _write_hb(tmp_path, "NATGASMINI", age_seconds=43.0, stage="CHAIN")
    cls, _, age = lv.classify("NATGASMINI", datetime.now(IST))
    assert cls == "HEARTBEAT_OK"
    assert 42.0 <= age <= 44.0


def test_slow_but_within_budget_is_healthy(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    _write_hb(tmp_path, "GOLDM", age_seconds=200.0, stage="MTF")
    cls, _, _ = lv.classify("GOLDM", datetime.now(IST))
    assert cls == "HEARTBEAT_OK"


def test_well_past_budget_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")
    cls, _, _ = lv.classify("NATGASMINI", datetime.now(IST))
    assert cls == "HEARTBEAT_STALE"


# -------- end-to-end via supervisor hook (dry_run) --------

def test_healthy_worker_does_not_get_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=30.0, stage="CHAIN")

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is False
    assert stop_calls == []
    assert rt.recovery_required is False


def test_flat_stale_worker_recycled_once(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")
    # no persisted position

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is True
    assert stop_calls == ["NATGASMINI"]   # exactly once
    assert rt.recovery_required is False


def test_active_position_stale_worker_goes_to_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    rt = sup.workers["GOLDM"]
    _write_hb(tmp_path, "GOLDM", age_seconds=900.0, stage="POSITION_MARK")
    _write_state(tmp_path, "GOLDM", active={"trade_id": "T_ACTIVE", "entry_time": "x"})

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is True
    assert stop_calls == ["GOLDM"]
    assert rt.recovery_required is True


def test_other_markets_unaffected_by_single_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    # NATGAS stale
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")
    # GOLDM and CRUDEOILM healthy
    _write_hb(tmp_path, "GOLDM", age_seconds=30.0, stage="CHAIN")
    _write_hb(tmp_path, "CRUDEOILM", age_seconds=30.0, stage="CHAIN")

    stop_calls = []
    monkeypatch.setattr(sup, "_stop_worker", lambda s, **kw: stop_calls.append(s.name))

    natgas_spec = _spec_for(sup, "NATGASMINI")
    goldm_spec = _spec_for(sup, "GOLDM")
    crude_spec = _spec_for(sup, "CRUDEOILM")

    r_natgas = sup._check_worker_liveness(sup.workers["NATGASMINI"], natgas_spec, datetime.now(IST))
    r_goldm = sup._check_worker_liveness(sup.workers["GOLDM"], goldm_spec, datetime.now(IST))
    r_crude = sup._check_worker_liveness(sup.workers["CRUDEOILM"], crude_spec, datetime.now(IST))

    assert r_natgas is True
    assert r_goldm is False
    assert r_crude is False
    assert stop_calls == ["NATGASMINI"]
