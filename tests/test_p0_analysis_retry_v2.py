"""Part 8 — analysis retry authority. Deterministic, no real analysis run."""
from __future__ import annotations

import sys
from datetime import date, datetime
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
from services.paper_orchestration.certification_halt_v2 import MarketState
from services.paper_orchestration.worker_session_authority_v2 import SessionAuthority

IST = ZoneInfo("Asia/Kolkata")
TODAY = date(2026, 9, 24)


def _make_sup(tmp_path, clock=None):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=False,
        log_dir="logs/supervisor",
        clock=clock or (lambda: datetime(2026, 9, 24, 15, 31, tzinfo=IST)),
        markets=("NIFTY",),
    )


def _spec():
    return next(s for s in WORKERS_V2 if s.name == "NIFTY")


def test_run_analysis_once_returns_success(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    def _fake_mod():
        class _M:
            analyze_market_day = staticmethod(lambda **k: {"ok": True})
            write_daily_report = staticmethod(lambda summary, repo_root: "report.md")
        return _M
    monkeypatch.setitem(
        sys.modules,
        "services.paper_orchestration.campaign_analysis_v2",
        _fake_mod(),
    )
    result = sup._run_analysis_once(_spec(), TODAY)
    assert result == "ANALYSIS_SUCCESS"


def test_run_analysis_once_returns_failure(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    def _fake_mod():
        def _boom(**k): raise RuntimeError("boom")
        class _M:
            analyze_market_day = staticmethod(_boom)
            write_daily_report = staticmethod(lambda *a, **k: "x")
        return _M
    monkeypatch.setitem(
        sys.modules,
        "services.paper_orchestration.campaign_analysis_v2",
        _fake_mod(),
    )
    result = sup._run_analysis_once(_spec(), TODAY)
    assert result == "ANALYSIS_FAILURE"


def test_dry_run_returns_dry_run(tmp_path):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    sup = AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=True,
        log_dir="logs/supervisor",
        clock=lambda: datetime(2026, 9, 24, 15, 31, tzinfo=IST),
        markets=("NIFTY",),
    )
    assert sup._run_analysis_once(_spec(), TODAY) == "ANALYSIS_DRY_RUN"


def test_failure_does_not_advance_last_analysis_date(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]
    calls = {"n": 0}
    def _fail(spec, day):
        calls["n"] += 1
        return "ANALYSIS_FAILURE"
    monkeypatch.setattr(sup, "_run_analysis_once", _fail)
    result = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert result == "ANALYSIS_FAILURE"
    assert rt.last_analysis_date is None
    assert calls["n"] == 1


def test_pass_marks_done_and_second_call_is_noop(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]
    calls = {"n": 0}
    def _ok(spec, day):
        calls["n"] += 1
        return "ANALYSIS_SUCCESS"
    monkeypatch.setattr(sup, "_run_analysis_once", _ok)
    r1 = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert r1 == "ANALYSIS_SUCCESS"
    assert rt.last_analysis_date == TODAY
    r2 = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert r2 == "ALREADY_DONE"
    assert calls["n"] == 1, "must not re-run after success"


def test_fail_then_pass_records_on_second_call(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]
    seq = ["ANALYSIS_FAILURE", "ANALYSIS_SUCCESS"]
    def _seq(spec, day):
        return seq.pop(0)
    monkeypatch.setattr(sup, "_run_analysis_once", _seq)
    r1 = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert r1 == "ANALYSIS_FAILURE"
    assert rt.last_analysis_date is None
    r2 = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert r2 == "ANALYSIS_SUCCESS"
    assert rt.last_analysis_date == TODAY


def test_dry_run_does_not_record(tmp_path):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    sup = AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=True,
        log_dir="logs/supervisor",
        clock=lambda: datetime(2026, 9, 24, 15, 31, tzinfo=IST),
        markets=("NIFTY",),
    )
    rt = sup.workers["NIFTY"]
    r = sup._run_analysis_and_record(rt, _spec(), TODAY)
    assert r == "ANALYSIS_DRY_RUN"
    assert rt.last_analysis_date is None


# ---------- tick() integration: COMPLETE branch retries -------------------

def test_complete_branch_retries_until_analysis_succeeds(tmp_path, monkeypatch):
    """Market hits 100. Analysis fails on first tick, succeeds on second.
    Only on the second tick should last_analysis_date advance."""
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]
    rt.process = None

    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "COMPLETE", 100),
    )

    seq = ["ANALYSIS_FAILURE", "ANALYSIS_SUCCESS"]
    def _seq(spec, day):
        return seq.pop(0)
    monkeypatch.setattr(sup, "_run_analysis_once", _seq)

    # First tick: analysis fails; last_analysis_date must remain None
    sup.tick()
    assert rt.last_analysis_date is None

    # Second tick: analysis succeeds; last_analysis_date advances
    sup.tick()
    assert rt.last_analysis_date == TODAY

    # Third tick: no more analysis runs (list would be empty otherwise)
    sup.tick()
    assert rt.last_analysis_date == TODAY


# ---------- tick() integration: session-done branch retries --------------

def test_session_done_branch_retries_until_analysis_succeeds(tmp_path, monkeypatch):
    sup = _make_sup(tmp_path)
    rt = sup.workers["NIFTY"]

    # Simulate session just closed with a running worker
    class _P:
        pid = 999
        def poll(self): return None
        def terminate(self): pass
        def kill(self): pass
    rt.process = _P()

    monkeypatch.setattr(
        sup_mod, "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 3),
    )
    monkeypatch.setattr(
        sup_mod, "_session_authority_for",
        lambda spec, now: SessionAuthority(False, False, False, None, True, "CLOSED", ""),
    )

    stop_calls = {"n": 0}
    def _stop(spec, grace_seconds=30.0):
        stop_calls["n"] += 1
        sup.workers[spec.name].process = None
    monkeypatch.setattr(sup, "_stop_worker", _stop)

    seq = ["ANALYSIS_FAILURE", "ANALYSIS_SUCCESS"]
    def _seq(spec, day):
        return seq.pop(0)
    monkeypatch.setattr(sup, "_run_analysis_once", _seq)

    sup.tick()
    assert rt.last_analysis_date is None
    # Second tick: process already None, but session is done — retry analysis
    sup.tick()
    assert rt.last_analysis_date == TODAY
