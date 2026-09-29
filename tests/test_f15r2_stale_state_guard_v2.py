"""F15-R2 M9c \u2014 stale stop artifacts + pre-start heartbeat.

Two bugs found in the 11:34 canary:

Bug A (stale stop request):
  Leftover NIFTY.request / SENSEX.request files from a prior canary
  caused every fresh worker spawn to exit immediately as a cooperative
  FLAT_ACK_EXIT. Supervisor classified this as UNEXPECTED_EXIT_ZERO and
  entered an infinite restart-backoff loop.

Bug B (pre-start heartbeat):
  Previous session heartbeat files (11:10 mtimes) were read by the
  supervisor at 11:36 while fresh workers were still booting. The
  watchdog classified them as HUNG_WORKER_DETECTED and recycled the
  workers before they ever wrote a heartbeat of their own.
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


# ---------- Bug A: stale stop artifacts ----------

def test_start_worker_clears_stale_request(tmp_path, monkeypatch):
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    stops = tmp_path / "logs" / "supervisor" / "stops"
    stops.mkdir(parents=True, exist_ok=True)
    req = stops / f"{spec.name}.request"
    ack = stops / f"{spec.name}.ack"
    req.write_text("STOP_NEW_ENTRIES", encoding="utf-8")
    ack.write_text("{}", encoding="utf-8")

    # In dry_run, _start_worker returns early — but our cleanup runs before
    # the market_worker_available check. Verify files are gone.
    outcome = sup._start_worker(spec)
    assert outcome.status == "DRY_RUN"
    assert not req.exists()
    assert not ack.exists()


def test_start_worker_cleanup_is_noop_when_absent(tmp_path):
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "GOLDM")
    # No stops dir exists yet — must not raise.
    outcome = sup._start_worker(spec)
    assert outcome.status == "DRY_RUN"


# ---------- Bug B: pre-start heartbeat must be ignored ----------

def test_pre_start_heartbeat_not_stale(tmp_path, monkeypatch):
    """Heartbeat written BEFORE worker's last_start_ist is not stale."""
    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(tmp_path / "logs" / "supervisor" / "heartbeats"),
    )
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]

    # Old heartbeat from 20 minutes ago
    _write_hb(tmp_path, "NATGASMINI", age_seconds=1200.0, stage="SLEEP")

    # Worker was started 30 seconds ago (AFTER the heartbeat)
    rt.last_start_ist = datetime.now(IST) - timedelta(seconds=30)

    stop_calls = []
    monkeypatch.setattr(
        sup, "_stop_worker",
        lambda s, **kw: stop_calls.append(s.name),
    )

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is False
    assert stop_calls == []


def test_post_start_stale_heartbeat_is_stale(tmp_path, monkeypatch):
    """Heartbeat written AFTER worker's last_start_ist IS checked normally."""
    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(tmp_path / "logs" / "supervisor" / "heartbeats"),
    )
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]

    # Worker was started 20 minutes ago
    rt.last_start_ist = datetime.now(IST) - timedelta(seconds=1200)

    # Heartbeat is only 900 seconds old (stale by threshold, but younger than start)
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")

    stop_calls = []
    monkeypatch.setattr(
        sup, "_stop_worker",
        lambda s, **kw: stop_calls.append(s.name),
    )

    result = sup._check_worker_liveness(rt, spec, datetime.now(IST))
    assert result is True
    assert stop_calls == ["NATGASMINI"]


def test_pre_start_only_applies_to_stale_classification(tmp_path, monkeypatch):
    """A fresh heartbeat is fine regardless of start time."""
    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(tmp_path / "logs" / "supervisor" / "heartbeats"),
    )
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    rt.last_start_ist = datetime.now(IST) - timedelta(seconds=1200)

    # Fresh heartbeat
    _write_hb(tmp_path, "NATGASMINI", age_seconds=30.0, stage="CHAIN")

    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False


def test_index_liveness_skip_still_active(tmp_path, monkeypatch):
    """The M9 index skip is unaffected by the M9c patch."""
    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(tmp_path / "logs" / "supervisor" / "heartbeats"),
    )
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NIFTY")
    rt = sup.workers["NIFTY"]
    _write_hb(tmp_path, "NIFTY", age_seconds=7200.0, stage="SESSION")

    stop_calls = []
    monkeypatch.setattr(
        sup, "_stop_worker",
        lambda s, **kw: stop_calls.append(s.name),
    )

    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is False
    assert stop_calls == []


def test_none_start_time_falls_through(tmp_path, monkeypatch):
    """If last_start_ist is None (never started), original behavior applies."""
    monkeypatch.setenv(
        "PAPER_HEARTBEAT_DIR",
        str(tmp_path / "logs" / "supervisor" / "heartbeats"),
    )
    sup = _sup(tmp_path)
    spec = _spec_for(sup, "NATGASMINI")
    rt = sup.workers["NATGASMINI"]
    rt.last_start_ist = None
    _write_hb(tmp_path, "NATGASMINI", age_seconds=900.0, stage="CHAIN")

    stop_calls = []
    monkeypatch.setattr(
        sup, "_stop_worker",
        lambda s, **kw: stop_calls.append(s.name),
    )

    assert sup._check_worker_liveness(rt, spec, datetime.now(IST)) is True
    assert stop_calls == ["NATGASMINI"]
