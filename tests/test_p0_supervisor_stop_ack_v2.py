"""Part 9b — supervisor ACK-aware stop + post-stop state validation. No real workers."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
from services.paper_orchestration.automated_paper_supervisor_v2 import (
    AutomatedPaperSupervisorV2,
    WORKERS_V2,
)

IST = ZoneInfo("Asia/Kolkata")


def _make_sup(tmp_path, monkeypatch, *, post_validation=True):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    sup = AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=False,
        log_dir="logs/supervisor",
        clock=lambda: datetime(2026, 9, 24, 15, 30, tzinfo=IST),
        markets=("NIFTY",),
    )
    sup.STOP_POST_VALIDATION_ENABLED = post_validation
    return sup


class _ControllableProc:
    def __init__(self, exit_after_ticks=None):
        self.pid = 99999
        self._rc = None
        self._ticks = 0
        self._exit_after = exit_after_ticks
    def poll(self):
        self._ticks += 1
        if self._exit_after is not None and self._ticks >= self._exit_after:
            self._rc = 0
        return self._rc
    def terminate(self): self._rc = 0
    def kill(self): self._rc = -9


def _spec():
    return next(s for s in WORKERS_V2 if s.name == "NIFTY")


def test_position_management_ack_extends_window(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()
    rt = sup.workers["NIFTY"]
    rt.process = _ControllableProc(exit_after_ticks=3)

    # Pre-write the ACK as the worker would
    ack_dir = tmp_path / "logs" / "supervisor" / "stops"
    ack_dir.mkdir(parents=True, exist_ok=True)
    ack = ack_dir / "NIFTY.ack"
    ack.write_text(json.dumps({
        "status": "POSITION_MANAGEMENT_ACTIVE",
        "has_active_position": True,
        "market": "NIFTY",
        "pid": 99999,
    }), encoding="utf-8")

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    # Suppress the delete of ack so it survives the first read
    real_unlink = Path.unlink
    def _noop_unlink(self, *a, **k):
        if str(self).endswith(".ack"):
            return
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", _noop_unlink)

    sup._stop_worker(spec, grace_seconds=1.0)

    assert any("POSITION_MANAGEMENT_WINDOW_EXTENDED" in m for m in logs), logs
    assert any("STOP_ACK status=POSITION_MANAGEMENT_ACTIVE" in m for m in logs)


def test_flat_ack_no_extension(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()
    rt = sup.workers["NIFTY"]
    rt.process = _ControllableProc(exit_after_ticks=3)

    ack_dir = tmp_path / "logs" / "supervisor" / "stops"
    ack_dir.mkdir(parents=True, exist_ok=True)
    ack = ack_dir / "NIFTY.ack"
    ack.write_text(json.dumps({
        "status": "FLAT_SAFE_TO_EXIT",
        "has_active_position": False,
    }), encoding="utf-8")

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    real_unlink = Path.unlink
    def _noop_unlink(self, *a, **k):
        if str(self).endswith(".ack"):
            return
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", _noop_unlink)

    sup._stop_worker(spec, grace_seconds=1.0)

    assert any("SAFE_TO_EXIT status=FLAT_SAFE_TO_EXIT" in m for m in logs), logs
    assert not any("WINDOW_EXTENDED" in m for m in logs)


def test_missing_ack_logs_timeout_no_extension(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()
    rt = sup.workers["NIFTY"]
    rt.process = _ControllableProc(exit_after_ticks=3)
    # No ACK written

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)

    sup._stop_worker(spec, grace_seconds=1.0)

    assert any("STOP_ACK_MISSING" in m for m in logs), logs
    assert not any("WINDOW_EXTENDED" in m for m in logs)


def test_forced_stop_logged_when_worker_wont_exit(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()
    rt = sup.workers["NIFTY"]
    # Never exits
    class _Stuck:
        pid = 999
        def poll(self): return None
        def terminate(self): pass
        def kill(self): pass
    rt.process = _Stuck()

    ack_dir = tmp_path / "logs" / "supervisor" / "stops"
    ack_dir.mkdir(parents=True, exist_ok=True)
    ack = ack_dir / "NIFTY.ack"
    ack.write_text(json.dumps({"status": "FLAT_SAFE_TO_EXIT",
                                "has_active_position": False}), encoding="utf-8")

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    real_unlink = Path.unlink
    def _noop_unlink(self, *a, **k):
        if str(self).endswith(".ack"):
            return
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", _noop_unlink)

    sup._stop_worker(spec, grace_seconds=0.1)

    assert any("ABNORMAL_SHUTDOWN_TIMEOUT" in m for m in logs), logs


# ---------- post-stop validation -------------------------------------------

def test_post_stop_validation_runs(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()

    from services.paper_orchestration import state_authority_readonly_v2 as sar
    monkeypatch.setattr(
        sar, "validate_market",
        lambda repo_root, market: sar.Verdict(market, True, "STATE_OK", ""),
    )

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    sup._validate_post_stop_state(spec, forced=False)
    assert any("STOP_STATE_VALIDATED" in m for m in logs), logs


def test_post_stop_validation_holds_on_bad_state(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()

    from services.paper_orchestration import state_authority_readonly_v2 as sar
    monkeypatch.setattr(
        sar, "validate_market",
        lambda repo_root, market: sar.Verdict(market, False, "STATE_COUNTER_INCOHERENT", ""),
    )

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    sup._validate_post_stop_state(spec, forced=False)
    assert any("STOP_STATE_HOLD" in m and "STATE_COUNTER_INCOHERENT" in m for m in logs), logs


def test_post_stop_validation_tolerates_exception(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, monkeypatch)
    spec = _spec()

    from services.paper_orchestration import state_authority_readonly_v2 as sar
    def _boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(sar, "validate_market", _boom)

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))
    sup._validate_post_stop_state(spec, forced=False)
    assert any("STOP_STATE_VALIDATION_RAISED" in m for m in logs), logs
