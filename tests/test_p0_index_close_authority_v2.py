"""Part 1 — index close authority + supervisor stop path."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration.automated_paper_supervisor_v2 import (
    AutomatedPaperSupervisorV2,
    WORKERS_V2,
)
from services.paper_orchestration.certification_halt_v2 import MarketState
from services.paper_orchestration.worker_session_authority_v2 import authority_for

IST = ZoneInfo("Asia/Kolkata")


def _spec(name):
    return next(s for s in WORKERS_V2 if s.name == name)


def _at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


# --- Part 1: index authority boundary tests ---

def test_index_nifty_before_open_no_session():
    # 2026-09-24 is Thursday. 09:14 is before open.
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 9, 14))
    assert a.calendar_authoritative is True
    assert a.session_open is False
    assert a.new_entries_allowed is False
    assert a.position_management_allowed is False


def test_index_nifty_at_open_session_active():
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 9, 15))
    assert a.session_open is True
    assert a.new_entries_allowed is True
    assert a.position_management_allowed is True


def test_index_nifty_mid_session():
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 10, 0))
    assert a.session_open is True
    assert a.position_management_allowed is True


def test_index_nifty_at_1529_still_open():
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 15, 29))
    assert a.session_open is True
    assert a.new_entries_allowed is True
    assert a.position_management_allowed is True


def test_index_nifty_at_1530_session_closed():
    # market_session_guard returns market_open=False at 15:30 exactly.
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 15, 30))
    assert a.session_open is False
    assert a.new_entries_allowed is False
    assert a.position_management_allowed is False, (
        "post-close must not permit position management; supervisor must stop"
    )


def test_index_nifty_at_1531_session_closed():
    a = authority_for(_spec("NIFTY"), _at(2026, 9, 24, 15, 31))
    assert a.session_open is False
    assert a.position_management_allowed is False


def test_index_sensex_mirrors_nifty_semantics():
    for hh, mm, want_open in [(9, 14, False), (9, 15, True), (10, 0, True),
                              (15, 29, True), (15, 30, False), (15, 31, False)]:
        a = authority_for(_spec("SENSEX"), _at(2026, 9, 24, hh, mm))
        assert a.session_open is want_open, f"SENSEX {hh}:{mm:02d} open={a.session_open}"


def test_index_holiday_no_session():
    # 2026-10-02 is Mahatma Gandhi Jayanti (NSE/BSE holiday)
    a = authority_for(_spec("NIFTY"), _at(2026, 10, 2, 10, 0))
    assert a.calendar_authoritative is True
    assert a.session_open is False
    assert a.new_entries_allowed is False
    assert a.position_management_allowed is False


# --- Part 1: supervisor stop-path integration ---

def _make_sup(tmp_path, *, markets, clock):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=True,
        log_dir="logs/supervisor",
        clock=clock,
        markets=markets,
    )


class _RunningProc:
    def __init__(self):
        self.pid = 424242
        self._rc = None
    def poll(self): return self._rc
    def terminate(self): self._rc = 0
    def kill(self): self._rc = -9


def test_supervisor_stops_index_worker_at_1530(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 3),
    )
    sup = _make_sup(tmp_path, markets=("NIFTY",),
                    clock=lambda: _at(2026, 9, 24, 15, 30))
    rt = sup.workers["NIFTY"]
    rt.process = _RunningProc()

    stop_called = {"n": 0}
    def _fake_stop(spec, grace_seconds=30.0):
        stop_called["n"] += 1
        sup.workers[spec.name].process = None
    monkeypatch.setattr(sup, "_stop_worker", _fake_stop)

    sup.tick()
    assert stop_called["n"] == 1, "worker must be stopped at 15:30"
    assert rt.last_expected_stop_ist is not None


def test_supervisor_keeps_index_worker_at_1529(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 3),
    )
    sup = _make_sup(tmp_path, markets=("NIFTY",),
                    clock=lambda: _at(2026, 9, 24, 15, 29))
    rt = sup.workers["NIFTY"]
    rt.process = _RunningProc()

    stop_called = {"n": 0}
    monkeypatch.setattr(sup, "_stop_worker",
                        lambda spec, grace_seconds=30.0: stop_called.__setitem__("n", stop_called["n"]+1))
    sup.tick()
    assert stop_called["n"] == 0, "worker must remain alive at 15:29"


def test_supervisor_does_not_start_index_before_open(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 0),
    )
    sup = _make_sup(tmp_path, markets=("NIFTY",),
                    clock=lambda: _at(2026, 9, 24, 9, 14))
    starts = {"n": 0}
    monkeypatch.setattr(sup, "_start_worker",
                        lambda spec: starts.__setitem__("n", starts["n"]+1) or None)
    sup.tick()
    assert starts["n"] == 0


def test_supervisor_does_not_start_index_on_holiday(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 0),
    )
    sup = _make_sup(tmp_path, markets=("NIFTY",),
                    clock=lambda: _at(2026, 10, 2, 10, 0))
    starts = {"n": 0}
    monkeypatch.setattr(sup, "_start_worker",
                        lambda spec: starts.__setitem__("n", starts["n"]+1) or None)
    sup.tick()
    assert starts["n"] == 0
