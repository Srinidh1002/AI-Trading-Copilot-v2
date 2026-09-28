"""F15-R2 Phase R2-5 — report terminology.

Proves the daily report clearly distinguishes:
    ENTRY_SIGNAL_DECISIONS   (cycle-tick BUY_CALL/BUY_PUT signals)
    ACTUAL_TRADE_OPENS       (closed + active at close)
    RAW_CLOSED_TRADES
    CERTIFICATION_ACCEPTED_TRADES
"""
from __future__ import annotations

import json
from datetime import date

from services.paper_orchestration.campaign_analysis_v2 import (
    analyze_market_day,
    write_daily_report,
)


def _seed(tmp_path, pred_rows, out_rows, state):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    (d / "nifty_predictions.jsonl").write_text(
        "\n".join(json.dumps(r) for r in pred_rows) + "\n", encoding="utf-8"
    )
    (d / "nifty_outcomes.jsonl").write_text(
        "\n".join(json.dumps(r) for r in out_rows) + "\n", encoding="utf-8"
    )
    (d / "nifty_experimental.json").write_text(json.dumps(state), encoding="utf-8")


PRED = [
    {"timestamp": "2026-09-28T10:00:00", "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {"timestamp": "2026-09-28T10:01:00", "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {"timestamp": "2026-09-28T10:02:00", "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {
        "timestamp": "2026-09-28T10:03:00",
        "action": "NO_TRADE",
        "readiness": "BLOCKED",
        "blockers": ["GATE_FAIL"],
    },
]

OUT = [
    {"trade_id": "T1", "timestamp": "2026-09-28T11:00:00", "net_pnl": 100.0,
     "first_touch_result": "T1_FIRST", "certification_countable": True,
     "certification_win": True, "certification_loss": False,
     "certification_trade_date": "2026-09-28"},
    {"trade_id": "T2", "timestamp": "2026-09-28T12:00:00", "net_pnl": -50.0,
     "first_touch_result": "SL_FIRST", "certification_countable": True,
     "certification_win": False, "certification_loss": True,
     "certification_trade_date": "2026-09-28"},
]


def test_summary_separates_signal_decisions_from_actual_opens(tmp_path):
    state = {
        "certification_counter": 2,
        "certification_epoch": "NS_CERT_20260916_V3",
        "active_trades": [{"trade_id": "T3"}],   # 1 open at close
    }
    _seed(tmp_path, PRED, OUT, state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    # cycle-tick signals: 3 BUY_PUT entries
    assert s["entry_signal_decisions"] == 3
    # actual opens: 2 closed + 1 active = 3
    assert s["actual_trade_opens"] == 3
    # raw closed outcomes: 2
    assert s["outcomes_today"] == 2
    # certification accepted: 2
    assert s["certification_countable"] == 2


def test_report_labels_are_disambiguated(tmp_path):
    state = {
        "certification_counter": 2,
        "certification_epoch": "NS_CERT_20260916_V3",
        "active_trades": [{"trade_id": "T3"}],
    }
    _seed(tmp_path, PRED, OUT, state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    p = write_daily_report(s, repo_root=str(tmp_path))
    text = open(p, encoding="utf-8").read()

    # signal decisions
    assert "Entry signal decisions (BUY_CALL/BUY_PUT): 3" in text
    # actual opens
    assert "Actual trade opens (closed + active at close): 3" in text
    # raw closed
    assert "Raw closed outcomes: 2" in text
    # certification accepted
    assert "Certification accepted trades: 2" in text
    # the ambiguous old label must NOT appear
    assert "Entry actions (BUY_CALL/BUY_PUT)" not in text
    assert "Certification countable:" not in text


def test_zero_case_still_reports_all_four_labels(tmp_path):
    state = {"certification_counter": 0, "active_trades": []}
    _seed(tmp_path, [], [], state)
    s = analyze_market_day(
        market="NIFTY", day=date(2026, 9, 28), repo_root=str(tmp_path)
    )
    assert s["entry_signal_decisions"] == 0
    assert s["actual_trade_opens"] == 0
    assert s["outcomes_today"] == 0
    assert s["certification_countable"] == 0
    p = write_daily_report(s, repo_root=str(tmp_path))
    text = open(p, encoding="utf-8").read()
    assert "Entry signal decisions (BUY_CALL/BUY_PUT): 0" in text
    assert "Actual trade opens (closed + active at close): 0" in text
    assert "Raw closed outcomes: 0" in text
    assert "Certification accepted trades: 0" in text
