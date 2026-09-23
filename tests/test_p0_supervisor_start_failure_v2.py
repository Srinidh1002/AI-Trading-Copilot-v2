"""Part 7 — supervisor start failure policy. Dummy workers only."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
from services.paper_orchestration.automated_paper_supervisor_v2 import (
    AutomatedPaperSupervisorV2,
    StartOutcome,
    WORKERS_V2,
)
from services.paper_orchestration.certification_halt_v2 import MarketState

IST = ZoneInfo("Asia/Kolkata")


def _make_sup(tmp_path, *, markets=None, clock=None):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        "FYERS_APP_ID=FAKE\nFYERS_ACCESS_TOKEN=TOKEN\n", encoding="utf-8"
    )
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=False,
        log_dir="logs/supervisor",
        clock=clock or (lambda: datetime(2026, 9, 24, 10, 0, tzinfo=IST)),
        markets=markets,
    )


def _spec(name="NIFTY"):
    return next(s for s in WORKERS_V2 if s.name == name)


class _FakeProc:
    def __init__(self):
        self.pid = 424242
        self._rc = None
    def poll(self): return self._rc
    def terminate(self): self._rc = 0
    def kill(self): self._rc = -9


# ---------- outcome tests ---------------------------------------------------

def test_dry_run_returns_dry_run(tmp_path):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    sup = AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=True,
        log_dir="logs/supervisor",
        clock=lambda: datetime(2026, 9, 24, 10, 0, tzinfo=IST),
    )
    outcome = sup._start_worker(_spec())
    assert isinstance(outcome, StartOutcome)
    assert outcome.status == "DRY_RUN"


def test_ownership_hold_returns_explicit_status(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: False)
    outcome = sup._start_worker(_spec())
    assert outcome.status == "START_OWNERSHIP_HOLD"


def test_env_failure_returns_explicit_status(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: True)
    # Force env build failure by not having .env with fresh creds; use a stub
    from services.broker import fyers_auth_v2 as auth
    def _boom(env_file, parent_env=None):
        raise auth.FyersAuthError("AUTH_MISSING", "missing")
    monkeypatch.setattr(auth, "build_fyers_child_env_v2", _boom)
    outcome = sup._start_worker(_spec())
    assert outcome.status == "START_ENV_FAILURE"
    assert outcome.note == "AUTH_MISSING"


def test_spawn_failure_returns_explicit_status(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: True)
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    def _boom(*_a, **_k):
        raise OSError("no such file")
    monkeypatch.setattr(sup_mod.subprocess, "Popen", _boom)
    outcome = sup._start_worker(_spec())
    assert outcome.status == "START_SPAWN_FAILURE"


def test_started_returns_process(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: True)
    monkeypatch.setattr(sup_mod.time, "sleep", lambda *_: None)
    fake = _FakeProc()
    monkeypatch.setattr(sup_mod.subprocess, "Popen", lambda *a, **k: fake)
    outcome = sup._start_worker(_spec())
    assert outcome.status == "STARTED"
    assert outcome.process is fake


# ---------- routing into restart authority ---------------------------------

def test_ownership_hold_pushes_backoff_no_failure_count(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    sup._record_ownership_hold(rt, now)
    assert rt.next_restart_ist == now + timedelta(seconds=sup.OWNERSHIP_HOLD_BACKOFF_SECONDS)
    assert rt.restart_failures == []


def test_env_failure_enters_failure_counter(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path, markets=("NIFTY",))
    # Force env fail on _start_worker call
    from services.broker import fyers_auth_v2 as auth
    def _boom(env_file, parent_env=None):
        raise auth.FyersAuthError("AUTH_MISSING", "missing")
    monkeypatch.setattr(auth, "build_fyers_child_env_v2", _boom)
    monkeypatch.setattr(sup_mod, "market_worker_available", lambda name: True)
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 0),
    )
    # Session open: mock authority
    from services.paper_orchestration.worker_session_authority_v2 import SessionAuthority
    monkeypatch.setattr(
        sup_mod, "_session_authority_for",
        lambda spec, now: SessionAuthority(True, True, True, None, True, "OPEN", ""),
    )

    sup.tick()
    rt = sup.workers["NIFTY"]
    assert len(rt.restart_failures) == 1
    assert rt.next_restart_ist is not None


def test_three_recorded_failures_open_circuit(tmp_path):
    """Three failures within the rolling window open the circuit.

    Tested directly on the accounting helper to avoid tick-timing flake.
    The tick route is proven by test_env_failure_enters_failure_counter.
    """
    sup = _make_sup(tmp_path, markets=("NIFTY",))
    rt = sup.workers["NIFTY"]
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    for i in range(3):
        sup._record_failure(rt, now + timedelta(seconds=i), -1)
    assert rt.circuit_open is True
    assert sup._may_start(rt, now + timedelta(hours=1)) is False


