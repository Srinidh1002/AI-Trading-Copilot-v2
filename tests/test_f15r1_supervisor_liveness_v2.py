"""Phase 6 — supervisor liveness integration tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.paper_orchestration.automated_paper_supervisor_v2 import (
    AutomatedPaperSupervisorV2,
    WorkerRuntimeV2,
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


def _write_hb(tmp_path, market, *, age_seconds=0.0, stage="CHAIN", has_pos=False, tid=None):
    hb_dir = tmp_path / "logs" / "supervisor" / "heartbeats"
    hb_dir.mkdir(parents=True, exist_ok=True)
    ts = (datetime.now(IST) - timedelta(seconds=age_seconds)).isoformat()
    payload = {
        "schema_version": 1, "market": market, "pid": 1, "worker_generation": 1,
        "timestamp": ts, "cycle_number": 1, "stage": stage,
        "stage_started_at": ts, "last_cycle_completed_at": None,
        "has_active_position": has_pos, "trade_id": tid,
        "execution_mode": "PAPER",
    }
    (hb_dir / (market + ".json")).write_text(json.dumps(payload), encoding="utf-8")


def _write_state(tmp_path, market, active=None):
    sd = tmp_path / "data" / "paper_trades"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"mcx_{market.lower()}_experimental.json").write_text(
        json.dumps({"active_position": active}), encoding="utf-8"
    )


# --- _check_worker_liveness in isolation (no live process needed) ---

def test_market_has_persisted_position_true(tmp_path):
    sup = _sup(tmp_path)
    _write_state(tmp_path, "CRUDEOILM", active={"trade_id": "T1", "entry_time": "x"})
    spec = _spec_for(sup, "CRUDEOILM")
    assert sup._market_has_persisted_position(spec) is True


def test_market_has_persisted_position_false(tmp_path):
    sup = _sup(tmp_path)
    _write_state(tmp_path, "GOLDM", active=None)
    spec = _spec_for(sup, "GOLDM")
    assert sup._market_has_persisted_position(spec) is False


def test_market_has_persisted_position_index_always_false(tmp_path):
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    assert sup._market_has_persisted_position(spec) is False


def test_liveness_returns_false_when_heartbeat_fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=5.0)
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False
    assert rt.recovery_required is False


def test_liveness_returns_false_when_no_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    rt = sup.workers["GOLDM"]
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False
    assert rt.recovery_required is False


def test_liveness_flat_stale_recycles_and_sets_flag_false(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    _write_hb(tmp_path, "NATGASMINI", age_seconds=600.0, stage="CHAIN")
    # No state file → no persisted position
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is True
    assert rt.recovery_required is False


def test_liveness_position_stale_sets_recovery_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_HEARTBEAT_DIR", str(tmp_path / "logs" / "supervisor" / "heartbeats"))
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    rt = sup.workers["GOLDM"]
    _write_hb(tmp_path, "GOLDM", age_seconds=600.0, stage="POSITION_MARK", has_pos=True, tid="T99")
    _write_state(tmp_path, "GOLDM", active={"trade_id": "T99", "entry_time": "x"})
    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is True
    assert rt.recovery_required is True


# --- _may_start recovery bypass ---

def test_may_start_circuit_open_blocks(tmp_path):
    sup = _sup(tmp_path)
    rt = WorkerRuntimeV2(spec=_spec_for(sup, "GOLDM"))
    rt.circuit_open = True
    assert sup._may_start(rt, datetime.now(IST)) is False


def test_may_start_recovery_required_bypasses_circuit(tmp_path):
    sup = _sup(tmp_path)
    rt = WorkerRuntimeV2(spec=_spec_for(sup, "GOLDM"))
    rt.circuit_open = True
    rt.recovery_required = True
    assert sup._may_start(rt, datetime.now(IST)) is True


# --- _consume_exit failure suppression during recovery ---

class _FakeProc:
    def __init__(self, rc):
        self._rc = rc
        self.pid = 99999
    def poll(self):
        return self._rc


def test_consume_exit_suppresses_failure_during_recovery(tmp_path):
    sup = _sup(tmp_path)
    rt = WorkerRuntimeV2(spec=_spec_for(sup, "NATGASMINI"))
    rt.recovery_required = True
    rt.process = _FakeProc(2)  # RUNTIME_FAILURE class
    before = len(rt.restart_failures)
    sup._consume_exit(rt, rt.spec, datetime.now(IST), datetime.now(IST).date(), expected_alive=True)
    assert len(rt.restart_failures) == before
    assert rt.process is None


def test_consume_exit_records_failure_without_recovery(tmp_path):
    sup = _sup(tmp_path)
    rt = WorkerRuntimeV2(spec=_spec_for(sup, "NATGASMINI"))
    rt.process = _FakeProc(2)
    before = len(rt.restart_failures)
    sup._consume_exit(rt, rt.spec, datetime.now(IST), datetime.now(IST).date(), expected_alive=True)
    assert len(rt.restart_failures) == before + 1


def test_consume_exit_single_count_per_generation(tmp_path):
    sup = _sup(tmp_path)
    rt = WorkerRuntimeV2(spec=_spec_for(sup, "NATGASMINI"))
    rt.process = _FakeProc(2)
    day = datetime.now(IST).date()
    sup._consume_exit(rt, rt.spec, datetime.now(IST), day, expected_alive=True)
    assert len(rt.restart_failures) == 1
    # Second call: rt.process is None, nothing consumed, no new failure.
    sup._consume_exit(rt, rt.spec, datetime.now(IST), day, expected_alive=True)
    assert len(rt.restart_failures) == 1
