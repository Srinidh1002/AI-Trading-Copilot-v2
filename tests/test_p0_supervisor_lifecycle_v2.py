"""Wave 1 — supervisor lifecycle, calendar authority, --markets validation.

Dummy workers only. No real trading code is spawned. Every test operates on
a tmp_path repo_root with a fake subprocess.Popen shape and a fake clock.
No live repository state, no .env, no FYERS, no network.
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

from services.paper_orchestration.automated_paper_supervisor_v2 import (  # noqa: E402
    AutomatedPaperSupervisorV2,
    WORKERS_V2,
)
from services.paper_orchestration.worker_session_authority_v2 import (  # noqa: E402
    SessionAuthority,
)

IST = ZoneInfo("Asia/Kolkata")


# ---------- fakes --------------------------------------------------------

class _FakeProc:
    """A stand-in for subprocess.Popen that answers poll() with a preset rc."""

    def __init__(self, rc=None):
        self._rc = rc
        self.pid = 10000 + id(self) % 10000

    def poll(self):
        return self._rc

    def set_rc(self, rc):
        self._rc = rc

    def terminate(self):
        self._rc = 0

    def kill(self):
        self._rc = -9

    def wait(self, timeout=None):
        return self._rc


def _authority(session_open, *, entries=None, pos_mgmt=True,
               close=datetime(2026, 9, 24, 15, 30, tzinfo=IST).time(),
               auth=True, status="OPEN", note=""):
    return SessionAuthority(
        session_open=session_open,
        new_entries_allowed=session_open if entries is None else entries,
        position_management_allowed=pos_mgmt,
        close_time=close,
        calendar_authoritative=auth,
        status=status,
        note=note,
    )


def _make_supervisor(tmp_path, *, markets=None, clock=None):
    """Construct a supervisor pointed at a tmp_path repo_root.

    Every worker slot starts with process=None (never started).
    """
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=True,  # never actually spawn
        log_dir="logs/supervisor",
        clock=clock or (lambda: datetime(2026, 9, 24, 10, 0, tzinfo=IST)),
        markets=markets,
    )


# ---------- classify ------------------------------------------------------

def test_classify_exit_zero_when_expected_alive_is_unexpected(tmp_path):
    sup = _make_supervisor(tmp_path)
    spec = WORKERS_V2[0]
    assert sup._classify_exit(spec, 0, expected_alive=True) == "UNEXPECTED_EXIT_ZERO"


def test_classify_exit_zero_when_not_expected_alive_is_clean_end(tmp_path):
    sup = _make_supervisor(tmp_path)
    spec = WORKERS_V2[0]
    assert sup._classify_exit(spec, 0, expected_alive=False) == "CLEAN_SESSION_END"


def test_classify_exit_1_and_2_are_startup_failure(tmp_path):
    sup = _make_supervisor(tmp_path)
    spec = WORKERS_V2[0]
    assert sup._classify_exit(spec, 1, expected_alive=True) == "STARTUP_FAILURE"
    assert sup._classify_exit(spec, 2, expected_alive=True) == "STARTUP_FAILURE"


def test_classify_exit_3_is_runtime_failure(tmp_path):
    sup = _make_supervisor(tmp_path)
    spec = WORKERS_V2[0]
    assert sup._classify_exit(spec, 3, expected_alive=True) == "RUNTIME_FAILURE"


def test_classify_exit_none_is_still_running(tmp_path):
    sup = _make_supervisor(tmp_path)
    spec = WORKERS_V2[0]
    assert sup._classify_exit(spec, None, expected_alive=True) == "STILL_RUNNING"


# ---------- circuit / backoff ---------------------------------------------

def test_three_failures_in_window_open_circuit(tmp_path):
    sup = _make_supervisor(tmp_path)
    rt = sup.workers["NIFTY"]
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    for _ in range(3):
        sup._record_failure(rt, now, 3)
    assert rt.circuit_open is True
    assert sup._may_start(rt, now) is False


def test_backoff_is_bounded(tmp_path):
    sup = _make_supervisor(tmp_path)
    rt = sup.workers["NIFTY"]
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    sup._record_failure(rt, now, 3)
    assert rt.next_restart_ist is not None
    delay_1 = (rt.next_restart_ist - now).total_seconds()
    assert delay_1 <= sup.MAX_RESTART_BACKOFF_SECONDS


def test_circuit_open_does_not_affect_other_market(tmp_path):
    sup = _make_supervisor(tmp_path)
    rt_nifty = sup.workers["NIFTY"]
    rt_sensex = sup.workers["SENSEX"]
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    for _ in range(3):
        sup._record_failure(rt_nifty, now, 3)
    assert rt_nifty.circuit_open is True
    assert rt_sensex.circuit_open is False
    assert sup._may_start(rt_sensex, now) is True


# ---------- healthy period ------------------------------------------------

def test_health_period_clears_failures_only_after_sustained_success(tmp_path):
    sup = _make_supervisor(tmp_path)
    rt = sup.workers["NIFTY"]
    t0 = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    rt.last_start_ist = t0
    sup._record_failure(rt, t0, 3)
    assert rt.restart_failures

    # 60 seconds later — not yet healthy
    sup._record_healthy(rt, t0 + timedelta(seconds=60))
    assert rt.restart_failures, "should not clear before HEALTHY_PERIOD"

    # 200 seconds later — past HEALTHY_PERIOD
    sup._record_healthy(rt, t0 + timedelta(seconds=200))
    assert not rt.restart_failures
    assert rt.next_restart_ist is None


# ---------- --markets validation -----------------------------------------

def _run_main(argv, monkeypatch, tmp_path):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod

    captured = {}

    class _NullSupervisor:
        def __init__(self, **kw):
            captured.update(kw)
        def tick(self):
            captured["tick_called"] = True
        def run_forever(self, poll_seconds=30.0):
            captured["run_called"] = True

    monkeypatch.setattr(sup_mod, "AutomatedPaperSupervisorV2", _NullSupervisor)
    monkeypatch.setattr(sup_mod, "_acquire_lock", lambda: None)
    monkeypatch.setattr(sys, "argv", ["supervisor"] + argv)
    rc = sup_mod._main()
    return rc, captured


def test_markets_validation_rejects_unknown(tmp_path, monkeypatch):
    rc, cap = _run_main(["--once", "--markets", "NIFTY,BOGUS"], monkeypatch, tmp_path)
    assert rc == 2
    assert "tick_called" not in cap
    assert "run_called" not in cap


def test_markets_validation_dedups_and_uppercases(tmp_path, monkeypatch):
    rc, cap = _run_main(["--once", "--markets", "nifty,NIFTY,SENSEX"], monkeypatch, tmp_path)
    assert rc == 0
    assert cap["markets"] == ("NIFTY", "SENSEX")
    assert cap["tick_called"] is True


def test_markets_validation_empty_after_normalize_is_none(tmp_path, monkeypatch):
    rc, cap = _run_main(["--once", "--markets", " , ,"], monkeypatch, tmp_path)
    assert rc == 0
    assert cap["markets"] is None


def test_markets_validation_allows_all_five(tmp_path, monkeypatch):
    rc, cap = _run_main(
        ["--once", "--markets", "NIFTY,SENSEX,CRUDEOILM,GOLDM,NATGASMINI"],
        monkeypatch, tmp_path,
    )
    assert rc == 0
    assert cap["markets"] == ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


# ---------- certification authority gate integration ----------------------

def test_cert_authority_hold_skips_market(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    from services.paper_orchestration.certification_halt_v2 import MarketState

    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    sup.workers["NIFTY"].process = _FakeProc(rc=None)  # pretend running

    def fake_state(name):
        return MarketState(name, "HOLD", None, "TEST_HOLD")
    monkeypatch.setattr(sup_mod, "_cert_market_state", fake_state)

    # In dry_run, _stop_worker only logs. Stub it so the assertion below
    # tests the real 'stop then skip' semantics of the tick() branch.
    def _fake_stop(spec, grace_seconds=30.0):
        sup.workers[spec.name].process = None
    monkeypatch.setattr(sup, "_stop_worker", _fake_stop)

    sup.tick()
    assert sup.workers["NIFTY"].process is None


def test_cert_authority_complete_stops_market_only(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod
    from services.paper_orchestration.certification_halt_v2 import MarketState

    sup = _make_supervisor(tmp_path, markets=("NIFTY", "SENSEX"))
    sup.workers["NIFTY"].process = _FakeProc(rc=None)
    sup.workers["SENSEX"].process = _FakeProc(rc=None)

    def fake_state(name):
        if name == "NIFTY":
            return MarketState(name, "COMPLETE", 100)
        return MarketState(name, "VALID_COUNTER", 2)

    monkeypatch.setattr(sup_mod, "_cert_market_state", fake_state)
    # Also stub authority so SENSEX does not start a real worker
    monkeypatch.setattr(
        sup_mod, "_session_authority_for",
        lambda spec, now: _authority(False, pos_mgmt=False, status="CLOSED"),
    )

    def _fake_stop(spec, grace_seconds=30.0):
        sup.workers[spec.name].process = None
    monkeypatch.setattr(sup, "_stop_worker", _fake_stop)

    sup.tick()
    assert sup.workers["NIFTY"].process is None
    # SENSEX should have been stopped because authority says CLOSED and no pos mgmt
    assert sup.workers["SENSEX"].process is None


# ---------- calendar authority gate ----------------------------------------

def test_calendar_hold_prevents_start(tmp_path, monkeypatch):
    from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod

    sup = _make_supervisor(tmp_path, markets=("NIFTY",))
    called = {"start": 0}
    def fake_start(spec):
        called["start"] += 1
        return None
    monkeypatch.setattr(sup, "_start_worker", fake_start)
    monkeypatch.setattr(
        sup_mod, "_session_authority_for",
        lambda spec, now: _authority(False, entries=False, pos_mgmt=False,
                                     status="CALENDAR_UNKNOWN", auth=False),
    )
    sup.tick()
    assert called["start"] == 0


def test_index_open_authority_uses_weekday(tmp_path):
    from services.paper_orchestration.worker_session_authority_v2 import authority_for
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    # 2026-09-24 is a Thursday, normal trading day
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    auth = authority_for(spec, now)
    assert auth.calendar_authoritative is True
    assert auth.session_open is True


def test_index_holiday_authority_is_closed(tmp_path):
    from services.paper_orchestration.worker_session_authority_v2 import authority_for
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    # 2026-10-02 is Mahatma Gandhi Jayanti in NSE_TRADING_HOLIDAYS_2026
    now = datetime(2026, 10, 2, 10, 0, tzinfo=IST)
    auth = authority_for(spec, now)
    assert auth.calendar_authoritative is True
    assert auth.session_open is False


def test_index_unknown_year_fails_closed(tmp_path):
    from services.paper_orchestration.worker_session_authority_v2 import authority_for
    spec = next(s for s in WORKERS_V2 if s.name == "NIFTY")
    now = datetime(2030, 9, 24, 10, 0, tzinfo=IST)
    auth = authority_for(spec, now)
    assert auth.calendar_authoritative is False
    assert auth.session_open is False


def test_mcx_authority_dispatch(tmp_path):
    from services.paper_orchestration.worker_session_authority_v2 import authority_for
    spec = next(s for s in WORKERS_V2 if s.name == "CRUDEOILM")
    # 2026-09-24 is Thursday, normal MCX day
    now = datetime(2026, 9, 24, 10, 0, tzinfo=IST)
    auth = authority_for(spec, now)
    # MCX is a session-authoritative return, whatever the current time says
    assert auth.calendar_authoritative is True or auth.status == "CALENDAR_UNKNOWN"


def test_bse_holiday_independent_from_nse(tmp_path):
    """BSE has the same 2026 list but the module is separate — verify both lookups."""
    from services.nse_holiday_calendar import get_nse_holiday_calendar
    from services.bse_holiday_calendar import get_bse_holiday_calendar
    nse = get_nse_holiday_calendar()
    bse = get_bse_holiday_calendar()
    check = datetime(2026, 10, 2, 12, 0, tzinfo=IST)
    assert nse.is_holiday(check) is True
    assert bse.is_holiday(check) is True
    # A known non-holiday: 2026-09-24 (Thursday)
    check2 = datetime(2026, 9, 24, 12, 0, tzinfo=IST)
    assert nse.is_holiday(check2) is False
    assert bse.is_holiday(check2) is False
