"""F15-R2 Phase R2-17 — reconciler compatibility with market-scoped IDs.

R2-3 changed index trade ID generation to TRD_<MARKET>_YYYYMMDD_HHMMSSffffff
and MCX to MCX_<PRODUCT>_YYYYMMDD_HHMMSSffffff. Legacy IDs
(TRD_YYYYMMDD_HHMMSS, MCX_YYYYMMDD_HHMMSS) still exist in old state files.

This file proves the active-state reconciler classifies both forms
correctly. The reconciler treats trade IDs as opaque strings — no
underscore parsing happens — so this is a regression guard, not a
behavioral change.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services.paper_orchestration import active_state_reconciler_v2 as rec

IST = timezone(timedelta(hours=5, minutes=30))


def _seed(tmp_path, market, state, outcome_ids=()):
    d = tmp_path / "data" / "paper_trades"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{market.lower()}_experimental.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    if outcome_ids:
        lines = [json.dumps({"trade_id": t}) for t in outcome_ids]
        (d / f"{market.lower()}_outcomes.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


def _read_state(tmp_path, market):
    return json.loads(
        (tmp_path / "data" / "paper_trades" / f"{market.lower()}_experimental.json")
        .read_text(encoding="utf-8")
    )


def _base_state(**over):
    s = {
        "market": "NIFTY",
        "certification_counter": 4,
        "certification_wins": 0,
        "certification_losses": 4,
        "counted_trade_ids": [],
        "active_trades": [],
        "orphaned_trades": [],
    }
    s.update(over)
    return s


def _active(tid, ftr="SL_FIRST"):
    return {"trade_id": tid, "first_touch_result": ftr, "first_touch_state": {}}


LEGACY = "TRD_20260928_095648"
CANON_NIFTY = "TRD_NIFTY_20260928_095648123456"


# -------- R2-17: legacy IDs still reconcile --------

def test_legacy_id_already_in_counted_ids_is_terminal(tmp_path):
    state = _base_state(
        active_trades=[_active(LEGACY)],
        counted_trade_ids=[LEGACY],
    )
    _seed(tmp_path, "NIFTY", state)
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    assert rows[0]["classification"] == rec.TERMINAL_ALREADY_RECORDED


def test_legacy_id_uninitialized_first_touch_is_orphan(tmp_path):
    state = _base_state(active_trades=[_active(LEGACY, ftr="")])
    _seed(tmp_path, "NIFTY", state)
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    assert rows[0]["classification"] == rec.STALE_RESTART_ORPHAN_PROVEN
    assert rows[0]["reason"] == "FIRST_TOUCH_UNINITIALIZED"


# -------- R2-17: canonical IDs reconcile identically --------

def test_canonical_id_already_in_counted_ids_is_terminal(tmp_path):
    state = _base_state(
        active_trades=[_active(CANON_NIFTY)],
        counted_trade_ids=[CANON_NIFTY],
    )
    _seed(tmp_path, "NIFTY", state)
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    assert rows[0]["classification"] == rec.TERMINAL_ALREADY_RECORDED


def test_canonical_id_uninitialized_first_touch_is_orphan(tmp_path):
    state = _base_state(active_trades=[_active(CANON_NIFTY, ftr="")])
    _seed(tmp_path, "NIFTY", state)
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    assert rows[0]["classification"] == rec.STALE_RESTART_ORPHAN_PROVEN


def test_canonical_id_in_outcomes_ledger_is_terminal(tmp_path):
    state = _base_state(active_trades=[_active(CANON_NIFTY)])
    _seed(tmp_path, "NIFTY", state, outcome_ids=[CANON_NIFTY])
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    assert rows[0]["classification"] == rec.TERMINAL_ALREADY_RECORDED
    assert "FOUND_IN_OUTCOMES" in rows[0]["reason"]


def test_legacy_and_canonical_coexist(tmp_path):
    state = _base_state(
        active_trades=[
            _active(LEGACY),
            _active(CANON_NIFTY, ftr=""),
        ],
        counted_trade_ids=[LEGACY],
    )
    _seed(tmp_path, "NIFTY", state)
    rows = rec.classify_market(str(tmp_path), "NIFTY")
    by_id = {r["trade_id"]: r["classification"] for r in rows}
    assert by_id[LEGACY] == rec.TERMINAL_ALREADY_RECORDED
    assert by_id[CANON_NIFTY] == rec.STALE_RESTART_ORPHAN_PROVEN


# -------- R2-17: apply path preserves invariants for both forms --------

def test_apply_archives_canonical_orphan_preserving_counters(tmp_path):
    state = _base_state(
        active_trades=[_active(CANON_NIFTY, ftr="")],
        certification_counter=4,
        certification_wins=0,
        certification_losses=4,
        counted_trade_ids=[],
    )
    _seed(tmp_path, "NIFTY", state)
    rpt = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    after = _read_state(tmp_path, "NIFTY")
    assert rpt["applied"] is True
    assert len(rpt["moved"]) == 1
    assert after["certification_counter"] == 4
    assert after["counted_trade_ids"] == []
    assert after["active_trades"] == []
    assert len(after["orphaned_trades"]) == 1
    assert after["orphaned_trades"][0]["trade_id"] == CANON_NIFTY


def test_apply_archives_legacy_orphan_preserving_counters(tmp_path):
    state = _base_state(
        active_trades=[_active(LEGACY, ftr="")],
        certification_counter=4,
        counted_trade_ids=[],
    )
    _seed(tmp_path, "NIFTY", state)
    rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    after = _read_state(tmp_path, "NIFTY")
    assert after["certification_counter"] == 4
    assert after["counted_trade_ids"] == []
    assert after["orphaned_trades"][0]["trade_id"] == LEGACY


def test_apply_idempotent_with_canonical_ids(tmp_path):
    state = _base_state(active_trades=[_active(CANON_NIFTY, ftr="")])
    _seed(tmp_path, "NIFTY", state)
    rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    rpt2 = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    assert rpt2["moved"] == []
    after = _read_state(tmp_path, "NIFTY")
    assert len(after["orphaned_trades"]) == 1


def test_apply_holds_canonical_trade_with_fresh_quote(tmp_path):
    now = datetime(2026, 9, 28, 20, 0, tzinfo=IST)
    fresh = (now - timedelta(minutes=5)).isoformat()
    active = _active(CANON_NIFTY, ftr="NONE")
    active["first_touch_state"] = {"last_valid_quote_time": fresh}
    state = _base_state(active_trades=[active])
    _seed(tmp_path, "NIFTY", state)
    rpt = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True, now=now)
    after = _read_state(tmp_path, "NIFTY")
    assert rpt["moved"] == []
    assert len(rpt["held"]) == 1
    assert len(after["active_trades"]) == 1
