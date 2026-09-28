"""Phase 11 — ledger schema parser tests."""
from __future__ import annotations

import json

from services.paper_orchestration import ledger_schema_v2 as ls


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---- summaries on inline fixtures that mirror the live schema ----

PRED_ROWS = [
    {"timestamp": "2026-09-28T14:58:21", "market": "NIFTY",
     "action": "BUY_PUT", "readiness": "READY", "blockers": []},
    {"timestamp": "2026-09-28T15:26:58", "market": "SENSEX",
     "action": "NO_TRADE", "readiness": "BLOCKED",
     "blockers": ["GATE_FAIL:session_state"]},
    {"timestamp": "2026-09-28T15:00:00", "market": "NIFTY",
     "action": "BUY_CALL", "readiness": "READY", "blockers": []},
]

OUT_ROWS = [
    # SL_FIRST, countable, cert loss
    {"trade_id": "T1", "market": "SENSEX", "net_pnl": -474.47,
     "exit_reason": "STOP_LOSS",
     "first_touch_result": "SL_FIRST",
     "certification_countable": True, "certification_win": False,
     "certification_loss": True, "certification_trade_date": "2026-09-28"},
    # AMBIGUOUS, not countable
    {"trade_id": "T2", "market": "NIFTY", "net_pnl": -620.58,
     "exit_reason": "STOP_LOSS",
     "first_touch_result": "AMBIGUOUS",
     "certification_countable": False, "certification_win": False,
     "certification_loss": False, "evidence_ambiguous": True,
     "certification_trade_date": "2026-09-28"},
    # NONE, countable
    {"trade_id": "T3", "market": "NIFTY", "net_pnl": -194.52,
     "exit_reason": "MARKET_CLOSE_3:28PM",
     "first_touch_result": "NONE",
     "certification_countable": True, "certification_win": False,
     "certification_loss": False, "certification_trade_date": "2026-09-28"},
]


def test_summarize_predictions_counts_entry_and_wait():
    s = ls.summarize_predictions(PRED_ROWS)
    assert s["total"] == 3
    assert s["entry_actions"] == 2
    assert s["wait_actions"] == 1
    assert s["other_actions"] == 0


def test_summarize_outcomes_separates_econ_and_cert():
    s = ls.summarize_outcomes(OUT_ROWS)
    assert s["total"] == 3
    # economic
    assert s["economic_wins"] == 0
    assert s["economic_losses"] == 3
    assert s["net_pnl"] == -1289.57
    # certification
    assert s["certification_countable"] == 2
    assert s["certification_wins"] == 0
    assert s["certification_losses"] == 1
    # first-touch histogram
    assert s["first_touch_SL_FIRST"] == 1
    assert s["first_touch_AMBIGUOUS"] == 1
    assert s["first_touch_NONE"] == 1
    assert s["first_touch_T1_FIRST"] == 0
    assert s["evidence_ambiguous"] == 1


def test_read_outcomes_missing_file_returns_empty(tmp_path):
    assert ls.read_outcomes(tmp_path, "NIFTY") == []


def test_read_outcomes_roundtrip(tmp_path):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True)
    _write_jsonl(d / "nifty_outcomes.jsonl", OUT_ROWS)
    rows = ls.read_outcomes(tmp_path, "NIFTY")
    assert len(rows) == 3
    assert rows[0]["trade_id"] == "T1"


def test_rows_for_day_filters_by_any_date_field():
    keep = ls.rows_for_day(OUT_ROWS, "2026-09-28")
    assert len(keep) == 3
    drop = ls.rows_for_day(OUT_ROWS, "2026-09-27")
    assert drop == []


def test_summarize_outcomes_empty_is_all_zero():
    s = ls.summarize_outcomes([])
    assert s["total"] == 0
    assert s["net_pnl"] == 0.0
    assert s["certification_countable"] == 0
    assert s["first_touch_SL_FIRST"] == 0
