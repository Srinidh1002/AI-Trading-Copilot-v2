"""Wave 3a — token authority (E), ACK-aware stop (F-sup), final analysis (J)."""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod  # noqa: E402
from services.paper_orchestration.automated_paper_supervisor_v2 import (  # noqa: E402
    AutomatedPaperSupervisorV2,
    WORKERS_V2,
)
from services.paper_orchestration.certification_halt_v2 import MarketState  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def _fake_env_file(tmp_path):
    envp = tmp_path / ".env"
    envp.write_text(
        "FYERS_APP_ID=FRESH_APP_ID\n"
        "FYERS_ACCESS_TOKEN=FRESH_TOKEN_VALUE\n"
        "FYERS_SECRET_ID=FRESH_SECRET\n"
        "FYERS_REDIRECT_URI=https://example/fresh\n",
        encoding="utf-8",
    )
    return envp


def _make_supervisor(tmp_path, *, markets=None, dry_run=False):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=dry_run,
        log_dir="logs/supervisor",
        clock=lambda: datetime(2026, 9, 24, 10, 0, tzinfo=IST),
        markets=markets,
    )


# ---------- E — token authority -------------------------------------------

def test_start_worker_uses_fresh_env_from_env_file(tmp_path, monkeypatch):
    _fake_env_file(tmp_path)
    monkeypatch.setenv("FYERS_APP_ID", "STALE_APP_ID")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "STALE_TOKEN_VALUE")

    captured = {}
    class _Cap:
        pid = 999
        def poll(self): return None
    def _fake_popen(args, **kw):
        captured["env"] = kw.get("env")
        return _Cap()
    monkeypatch.setattr(sup_mod.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        sup_mod, "market_worker_available", lambda name: True
    )

    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    proc = sup._start_worker(spec)

    assert proc is not None
    env = captured["env"]
    assert env["FYERS_APP_ID"] == "FRESH_APP_ID"
    assert env["FYERS_ACCESS_TOKEN"] == "FRESH_TOKEN_VALUE"
    assert env["FYERS_SECRET_ID"] == "FRESH_SECRET"
    assert env["FYERS_REDIRECT_URI"] == "https://example/fresh"


def test_start_worker_fails_closed_when_env_file_missing(tmp_path, monkeypatch):
    # .env does not exist
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: True)
    called = {"popen": 0}
    def _fake_popen(*_a, **_k):
        called["popen"] += 1
        raise AssertionError("Popen should not be called")
    monkeypatch.setattr(sup_mod.subprocess, "Popen", _fake_popen)

    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    outcome = sup._start_worker(spec)
    # Part 7: _start_worker returns StartOutcome, not None
    assert outcome.status == "START_ENV_FAILURE"
    assert outcome.process is None
    assert called["popen"] == 0


# ---------- F supervisor — ACK-aware stop --------------------------------

class _StoppableProc:
    def __init__(self, exit_after=0):
        self.pid = 12345
        self._rc = None
        self._tick = 0
        self._exit_after = exit_after
    def poll(self):
        self._tick += 1
        if self._tick >= self._exit_after:
            self._rc = 0
        return self._rc
    def terminate(self): self._rc = 0
    def kill(self): self._rc = -9


def test_stop_worker_observes_ack_file(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    rt = sup.workers["NIFTY"]
    proc = _StoppableProc(exit_after=4)
    rt.process = proc

    # Pre-create the ACK file that the worker would write
    ack_dir = tmp_path / "logs" / "supervisor" / "stops"
    ack_dir.mkdir(parents=True, exist_ok=True)
    ack = ack_dir / "NIFTY.ack"

    # Patch the ACK check so `exists()` returns True on the second poll
    real_exists = Path.exists
    counter = {"n": 0}
    def _patched_exists(self):
        if str(self).endswith(".ack"):
            counter["n"] += 1
            return counter["n"] >= 2
        return real_exists(self)
    monkeypatch.setattr(Path, "exists", _patched_exists)

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))

    sup._stop_worker(spec, grace_seconds=2.0)

    assert any("STOP_ACK received" in m for m in logs), logs


def test_stop_worker_forced_when_no_ack(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    rt = sup.workers["NIFTY"]
    # Never exits on its own
    class _Stuck:
        pid = 99999
        def poll(self): return None
        def terminate(self): pass
        def kill(self): pass
    rt.process = _Stuck()

    # Shorten timings for the test
    monkeypatch.setattr(sup, "STOP_ACK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)

    logs = []
    monkeypatch.setattr(sup, "_log", lambda m: logs.append(m))

    sup._stop_worker(spec, grace_seconds=0.5)

    assert any("ABNORMAL_SHUTDOWN_TIMEOUT" in m for m in logs), logs
    assert any("ack=False" in m for m in logs), logs


# ---------- J — final analysis once --------------------------------------

def test_complete_branch_runs_final_analysis_once(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    rt = sup.workers["NIFTY"]
    rt.process = None
    rt.last_analysis_date = None

    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "COMPLETE", 100),
    )
    calls = []
    monkeypatch.setattr(
        sup, "_run_analysis_once",
        lambda spec_, day: calls.append((spec_.name, day)),
    )
    # Session authority not consulted for COMPLETE branch

    sup.tick()
    assert len(calls) == 1
    assert calls[0][0] == "NIFTY"

    # Second tick must not repeat
    sup.tick()
    assert len(calls) == 1, "analysis ran more than once"
