"""Phase 11 — daily audit parser (campaign_analysis_v2) tests."""
from __future__ import annotations

import json
from datetime import date

from services.paper_orchestration.campaign_analysis_v2 import (
    analyze_market_day,
    write_daily_report,
)


def _seed(tmp_path, market, pred_rows, out_rows, state_dict):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    lower = market.lower()
    prefix = "mcx_" if market in ("CRUDEOILM", "GOLDM", "NATGASMINI") else ""
    if pred_rows is not None:
        (d / f"{prefix}{lower}_predictions.jsonl").write_text(
            "\n".join(json.dumps(r) for r in pred_rows) + "\n",
            encoding="utf-8",
        )
    if out_rows is not None:
        (d / f"{prefix}{lower}_outcomes.jsonl").write_text(
            "\n".join(json.dumps(r) for r in out_rows) + "\n",
            encoding="utf-8",
        )
    (d / f"{prefix}{lower}_experimental.json").write_text(
        json.dumps(state_dict), encoding="utf-8"
    )


PRED = [
    {"timestamp": "2026-09-28T14:58:21", "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {"timestamp": "2026-09-28T15:10:00", "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {"timestamp": "2026-09-28T15:26:58", "action": "NO_TRADE", "readiness": "BLOCKED",
     "blockers": ["GATE_FAIL:session_state", "GATE_FAIL:spot_freshness"]},
]

OUT = [
    {"trade_id": "T1", "timestamp": "2026-09-28T14:53:54",
     "net_pnl": -620.58, "exit_reason": "STOP_LOSS",
     "first_touch_result": "AMBIGUOUS", "evidence_ambiguous": True,
     "certification_countable": False,
     "certification_win": False, "certification_loss": False,
     "certification_trade_date": "2026-09-28"},
    {"trade_id": "T2", "timestamp": "2026-09-28T15:28:02",
     "net_pnl": -194.52, "exit_reason": "MARKET_CLOSE_3:28PM",
     "first_touch_result": "NONE",
     "certification_countable": True,
     "certification_win": False, "certification_loss": True,
     "certification_trade_date": "2026-09-28"},
    {"trade_id": "T3", "timestamp": "2026-09-28T11:33:15",
     "net_pnl": 500.0, "exit_reason": "T1",
     "first_touch_result": "T1_FIRST",
     "certification_countable": True,
     "certification_win": True, "certification_loss": False,
     "certification_trade_date": "2026-09-28"},
    # previous day — should be filtered out
    {"trade_id": "OLD", "timestamp": "2026-09-27T14:00:00",
     "net_pnl": 999.0, "first_touch_result": "T1_FIRST",
     "certification_countable": True,
     "certification_win": True, "certification_loss": False,
     "certification_trade_date": "2026-09-27"},
]


def test_index_market_analyze_uses_active_trades_list(tmp_path):
    state = {
        "certification_counter": 4,
        "certification_epoch": "NS_CERT_20260916_V3",
        "active_trades": [{"trade_id": "X1"}, {"trade_id": "X2"}],
    }
    _seed(tmp_path, "NIFTY", PRED, OUT, state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    assert s["decisions_today"] == 3
    assert s["entry_signal_decisions"] == 2
    assert s["wait_actions"] == 1
    assert s["outcomes_today"] == 3
    assert s["wins"] == 1           # econ wins (T3 only)
    assert s["losses"] == 2         # econ losses (T1, T2)
    assert s["first_t1"] == 1
    assert s["first_sl"] == 0
    assert s["first_ambiguous"] == 1
    assert s["first_none"] == 1
    assert s["certification_countable"] == 2
    assert s["certification_wins"] == 1
    assert s["certification_losses"] == 1
    assert s["counter"] == 4
    assert s["active_position"] is True
    assert s["active_position_count"] == 2


def test_mcx_market_analyze_uses_active_position_dict(tmp_path):
    state = {
        "certification_counter": 0,
        "certification_epoch": "MCX_CERT_V1",
        "active_position": {"trade_id": "M1", "entry_time": "x"},
    }
    _seed(tmp_path, "CRUDEOILM", PRED, OUT, state)
    s = analyze_market_day(
        market="CRUDEOILM", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    assert s["active_position"] is True
    assert s["active_position_count"] == 1
    assert s["decisions_today"] == 3


def test_no_active_position(tmp_path):
    state = {"certification_counter": 0, "active_position": None}
    _seed(tmp_path, "NIFTY", [], [], state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    assert s["active_position"] is False
    assert s["active_position_count"] == 0


def test_write_daily_report_contains_cert_section(tmp_path):
    state = {
        "certification_counter": 4,
        "certification_epoch": "NS_CERT_20260916_V3",
        "active_trades": [{"trade_id": "X1"}],
    }
    _seed(tmp_path, "NIFTY", PRED, OUT, state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    p = write_daily_report(s, repo_root=str(tmp_path))
    text = open(p, encoding="utf-8").read()
    assert "Economic wins: 1" in text
    assert "Economic losses: 2" in text
    assert "Certification accepted trades: 2" in text
    assert "Certification wins: 1" in text
    assert "Certification losses: 1" in text
    assert "T1_FIRST: 1" in text
    assert "SL_FIRST: 0" in text
    assert "AMBIGUOUS: 1" in text
    assert "NONE: 1" in text
    assert "Monitoring-gap ambiguity: 1" in text
    assert "Raw closed outcomes: 3" in text


def test_prev_day_rows_are_excluded(tmp_path):
    state = {"certification_counter": 0}
    _seed(tmp_path, "NIFTY", [], OUT, state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    # OLD row filtered out
    assert s["outcomes_today"] == 3
