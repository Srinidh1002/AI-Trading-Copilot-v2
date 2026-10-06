"""R19-B operational-integrity regression tests.

Offline only: synthetic process/state authority, no provider/network calls.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration import automated_paper_supervisor_v2 as sup_mod  # noqa: E402
from services.paper_orchestration.automated_paper_supervisor_v2 import (  # noqa: E402
    AutomatedPaperSupervisorV2,
    StartOutcome,
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


class _Proc:
    def __init__(self, rc=0, pid=19001):
        self._rc = rc
        self.pid = pid

    def poll(self):
        return self._rc

    def terminate(self):
        self._rc = 0

    def kill(self):
        self._rc = -9


def _sup(tmp_path, clock):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    return AutomatedPaperSupervisorV2(
        repo_root=str(tmp_path),
        python_exe=sys.executable,
        dry_run=False,
        log_dir="logs/supervisor",
        clock=clock,
        markets=("NIFTY",),
    )


def _open_authority(monkeypatch):
    monkeypatch.setattr(
        sup_mod,
        "_cert_market_state",
        lambda name: MarketState(name, "VALID_COUNTER", 0),
    )
    auth = SessionAuthority(True, True, True, None, True, "OPEN", "")
    monkeypatch.setattr(
        sup_mod,
        "_session_authority_for",
        lambda spec, now: auth,
    )


def test_clean_close_latches_same_day_and_prevents_restart(tmp_path, monkeypatch):
    t0 = datetime(2026, 10, 6, 15, 28, 30, tzinfo=IST)
    clock = _Clock(t0)
    sup = _sup(tmp_path, clock)
    _open_authority(monkeypatch)

    rt = sup.workers["NIFTY"]
    rt.process = _Proc(rc=0)
    rt.last_start_ist = datetime(2026, 10, 6, 9, 15, tzinfo=IST)

    monkeypatch.setattr(sup, "_market_has_persisted_position", lambda spec: False)
    monkeypatch.setattr(sup, "_run_analysis_and_record", lambda *args: "OK")

    starts = []
    monkeypatch.setattr(
        sup,
        "_start_worker",
        lambda spec: starts.append(spec.name) or StartOutcome("STARTED", _Proc(None)),
    )

    sup.tick()

    assert rt.last_exit_status == "CLEAN_SESSION_END"
    assert rt.session_terminal_date == date(2026, 10, 6)
    assert rt.process is None
    assert starts == []

    clock.now = datetime(2026, 10, 6, 15, 29, 0, tzinfo=IST)
    sup.tick()

    assert rt.process is None
    assert starts == []


def test_new_day_clears_terminal_latch(tmp_path, monkeypatch):
    t0 = datetime(2026, 10, 7, 9, 20, tzinfo=IST)
    clock = _Clock(t0)
    sup = _sup(tmp_path, clock)
    _open_authority(monkeypatch)

    rt = sup.workers["NIFTY"]
    rt.runtime_session_date = date(2026, 10, 6)
    rt.session_terminal_date = date(2026, 10, 6)

    monkeypatch.setattr(sup, "_market_has_persisted_position", lambda spec: False)
    monkeypatch.setattr(sup, "_run_analysis_and_record", lambda *args: "OK")

    proc = _Proc(None)
    monkeypatch.setattr(
        sup,
        "_start_worker",
        lambda spec: StartOutcome("STARTED", proc),
    )

    sup.tick()

    assert rt.runtime_session_date == date(2026, 10, 7)
    assert rt.session_terminal_date is None
    assert rt.process is proc


def test_close_window_exit_with_persisted_position_is_hold_not_clean(tmp_path, monkeypatch):
    t0 = datetime(2026, 10, 6, 15, 28, 30, tzinfo=IST)
    clock = _Clock(t0)
    sup = _sup(tmp_path, clock)
    _open_authority(monkeypatch)

    rt = sup.workers["NIFTY"]
    rt.process = _Proc(rc=0)

    monkeypatch.setattr(sup, "_market_has_persisted_position", lambda spec: True)
    monkeypatch.setattr(sup, "_run_analysis_and_record", lambda *args: "OK")

    starts = []
    monkeypatch.setattr(
        sup,
        "_start_worker",
        lambda spec: starts.append(spec.name) or StartOutcome("STARTED", _Proc(None)),
    )

    sup.tick()

    assert rt.last_exit_status == "UNRESOLVED_ACTIVE_POSITION"
    assert rt.recovery_required is True
    assert rt.session_terminal_date is None
    assert rt.process is None
    assert starts == []



def test_persisted_position_blocks_fresh_worker_start_after_supervisor_restart(
    tmp_path, monkeypatch
):
    t0 = datetime(2026, 10, 6, 11, 0, tzinfo=IST)
    clock = _Clock(t0)
    sup = _sup(tmp_path, clock)
    _open_authority(monkeypatch)

    rt = sup.workers["NIFTY"]
    assert rt.process is None

    monkeypatch.setattr(sup, "_market_has_persisted_position", lambda spec: True)
    monkeypatch.setattr(sup, "_run_analysis_and_record", lambda *args: "OK")

    starts = []
    monkeypatch.setattr(
        sup,
        "_start_worker",
        lambda spec: starts.append(spec.name) or StartOutcome("STARTED", _Proc(None)),
    )

    sup.tick()

    assert rt.recovery_required is True
    assert rt.process is None
    assert starts == []

def test_index_daily_risk_fields_are_saved_and_restored():
    source = (REPO / "src" / "target_focused_bot.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    fields = (
        "daily_risk_date",
        "last_exit_time",
        "last_exit_direction",
        "same_direction_stops",
        "daily_realized_loss",
        "daily_trade_count",
    )

    save_start = source.index("def save_state")
    load_start = source.index("def load_state", save_start)
    save_src = source[save_start:load_start]
    load_src = source[load_start:source.index("def activate_current_certification_epoch_if_safe", load_start)]

    for field in fields:
        assert repr(field) in save_src or f'"{field}"' in save_src
        assert repr(field) in load_src or f'"{field}"' in load_src

    assert "_risk_day == _today_iso" in load_src
    assert "self.daily_realized_loss = 0.0" in load_src
    assert "self.daily_trade_count = 0" in load_src


def test_prior_session_active_trade_fails_closed_instead_of_silent_purge():
    source = (REPO / "src" / "target_focused_bot.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    load_start = source.index("def load_state")
    load_src = source[
        load_start:source.index(
            "def activate_current_certification_epoch_if_safe",
            load_start,
        )
    ]

    assert "PRIOR_SESSION_ACTIVE_REQUIRES_RECONCILIATION" in load_src
    assert "ORPHAN_PURGE:" not in load_src
    assert "del self.active_trades" not in load_src


def test_session_close_without_bid_is_preserved_as_unresolved():
    source = (REPO / "src" / "target_focused_bot.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "_close_deadline = self.MARKET_CLOSE" in source
    assert "SESSION_CLOSE_UNRESOLVED" in source
    assert "session_close_unresolved" in source
    assert "manual reconciliation required" in source
