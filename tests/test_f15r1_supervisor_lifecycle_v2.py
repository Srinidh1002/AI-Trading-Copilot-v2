"""F15-R1 — supervisor process-generation exit accounting.

Every test uses synthetic state and a fake clock. No real subprocess,
no live state, no network.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod  # noqa: E402
from services.paper_orchestration.automated_paper_supervisor_v2 import (  # noqa: E402
    AutomatedPaperSupervisorV2,
    StartOutcome,
    WORKERS_V2,
)
from services.paper_orchestration.certification_halt_v2 import MarketState  # noqa: E402
from services.paper_orchestration.worker_session_authority_v2 import (  # noqa: E402
    SessionAuthority,
)

IST = ZoneInfo("Asia/Kolkata")


class _Clock:
    def __init__(self, dt):
        self.now = dt

    def __call__(self):
        return self.now


class _FakeProc:
    def __init__(self, rc=None, pid=424242):
        self._rc = rc
        self.pid = pid

    def poll(self):
        return self._rc

    def terminate(self):
        self._rc = 0

    def kill(self):
        self._rc = -9


def _make_sup(tmp_path, clock, markets=("NIFTY",)):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=False,
        log_dir="logs/supervisor",
        clock=clock,
        markets=markets,
    )


def _stub_authorities(monkeypatch, session_open=True, auth_ok=True):
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 0),
    )
    if session_open:
        auth = SessionAuthority(True, True, True, None, auth_ok, "OPEN", "")
    else:
        auth = SessionAuthority(False, False, False, None, auth_ok, "CLOSED", "")
    monkeypatch.setattr(
        sup_mod, "_session_authority_for",
        lambda spec, now: auth,
    )


# ---------- A. one dead Popen cannot produce 3 failures ----------

def test_single_dead_popen_counts_once(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch)
    rt = sup.workers["NIFTY"]
    rt.process = _FakeProc(rc=1)
    rt.last_start_ist = t0 - timedelta(seconds=5)

    sup.tick()
    assert len(rt.restart_failures) == 1
    assert rt.process is None
    assert rt.consumed_exit_count == 1

    # Same dead process is gone; tick twice more, nothing new consumed.
    clock.now = t0 + timedelta(seconds=10)
    sup.tick()
    clock.now = t0 + timedelta(seconds=20)
    sup.tick()
    assert len(rt.restart_failures) == 1
    assert rt.consumed_exit_count == 1
    assert rt.circuit_open is False


# ---------- B. three separate generations open circuit ----------

def test_three_generations_open_circuit(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch)

    generations = [_FakeProc(rc=1, pid=1001),
                   _FakeProc(rc=1, pid=1002),
                   _FakeProc(rc=1, pid=1003)]
    spawn_iter = iter(generations)

    def _fake_start(spec):
        try:
            proc = next(spawn_iter)
        except StopIteration:
            return StartOutcome("START_SPAWN_FAILURE", note="no more")
        return StartOutcome("STARTED", process=proc)

    sup._start_worker = _fake_start

    rt = sup.workers["NIFTY"]
    # Generation 1
    rt.process = _FakeProc(rc=1, pid=1000)
    sup.tick()
    assert len(rt.restart_failures) == 1
    assert rt.circuit_open is False

    # Advance past backoff, start generation 2
    clock.now = t0 + timedelta(seconds=40)
    sup.tick()  # starts gen 2
    assert rt.process is not None
    assert rt.generation_id == 1

    # Gen 2 dies
    clock.now = t0 + timedelta(seconds=50)
    sup.tick()
    assert len(rt.restart_failures) == 2
    assert rt.circuit_open is False

    # Advance past backoff, start gen 3
    clock.now = t0 + timedelta(seconds=180)
    sup.tick()
    assert rt.process is not None
    assert rt.generation_id == 2

    # Gen 3 dies
    clock.now = t0 + timedelta(seconds=190)
    sup.tick()
    assert len(rt.restart_failures) == 3
    assert rt.circuit_open is True


# ---------- C. clean rc=0 outside grace with expected stop ----------

def test_clean_rc0_outside_session_not_counted_as_failure(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 16, 0, tzinfo=IST)  # after 15:30 close
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=False)
    rt = sup.workers["NIFTY"]
    rt.process = _FakeProc(rc=0)
    rt.last_start_ist = t0 - timedelta(hours=1)

    sup.tick()
    assert rt.restart_failures == []
    assert rt.process is None
    assert rt.consumed_exit_count == 1
    assert rt.last_exit_status == "CLEAN_SESSION_END"


# ---------- D. unexpected rc=0 in-session counts once ----------

def test_unexpected_rc0_in_session_counts_once(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    rt = sup.workers["NIFTY"]
    rt.process = _FakeProc(rc=0)
    rt.last_start_ist = t0 - timedelta(seconds=30)

    sup.tick()
    assert len(rt.restart_failures) == 1
    assert rt.process is None
    assert rt.last_exit_status == "UNEXPECTED_EXIT_ZERO"

    clock.now = t0 + timedelta(seconds=10)
    sup.tick()
    assert len(rt.restart_failures) == 1


# ---------- E. ownership hold does not increment crash count ----------

def test_ownership_hold_not_counted(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    sup._start_worker = lambda spec: StartOutcome("START_OWNERSHIP_HOLD")
    rt = sup.workers["NIFTY"]

    sup.tick()
    assert rt.restart_failures == []
    assert rt.circuit_open is False
    assert rt.next_restart_ist is not None
    assert rt.next_restart_ist > t0


# ---------- F. spawn failure is counted ----------

def test_spawn_failure_counted(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    sup._start_worker = lambda spec: StartOutcome("START_SPAWN_FAILURE", note="x")
    rt = sup.workers["NIFTY"]

    sup.tick()
    assert len(rt.restart_failures) == 1
    assert rt.next_restart_ist is not None


# ---------- G. close-window: 15:28 legitimate exit ----------

def test_close_grace_1530_clean_exit(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 15, 28, 30, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    rt = sup.workers["NIFTY"]
    rt.process = _FakeProc(rc=0)
    rt.last_start_ist = t0 - timedelta(hours=6)

    sup.tick()
    assert rt.last_exit_status == "CLEAN_SESSION_END"
    assert rt.restart_failures == []
    assert rt.circuit_open is False
    assert rt.process is None


# ---------- H. new authoritative day resets circuit + backoff ----------

def test_new_day_resets_circuit_and_backoff(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    rt = sup.workers["NIFTY"]
    rt.circuit_open = True
    rt.restart_failures = [t0 - timedelta(seconds=60)]
    rt.next_restart_ist = t0 + timedelta(hours=1)
    rt.runtime_session_date = date(2026, 9, 28)

    sup._start_worker = lambda spec: StartOutcome("STARTED", process=_FakeProc())

    # Next authoritative trading day
    clock.now = datetime(2026, 9, 29, 9, 20, tzinfo=IST)
    sup.tick()
    assert rt.circuit_open is False
    assert rt.restart_failures == []
    assert rt.next_restart_ist is None
    assert rt.runtime_session_date == date(2026, 9, 29)
    assert rt.process is not None


# ---------- I. exit_history preserved across session reset ----------

def test_exit_history_preserved_across_session_reset(tmp_path, monkeypatch):
    t0 = datetime(2026, 9, 28, 10, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _make_sup(tmp_path, clock)
    _stub_authorities(monkeypatch, session_open=True)
    rt = sup.workers["NIFTY"]
    rt.process = _FakeProc(rc=1)
    rt.last_start_ist = t0 - timedelta(seconds=5)

    sup.tick()
    first_day_history_len = len(rt.exit_history)
    assert first_day_history_len == 1

    clock.now = datetime(2026, 9, 29, 9, 20, tzinfo=IST)
    sup._start_worker = lambda spec: StartOutcome("STARTED", process=_FakeProc())
    sup.tick()
    # Exit history must remain at 1 even though the new day started.
    assert len(rt.exit_history) == first_day_history_len
