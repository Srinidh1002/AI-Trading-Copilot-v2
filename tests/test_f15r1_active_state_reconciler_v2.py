"""Phase 10 — active-state reconciler tests."""
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
        "counted_trade_ids": ["TRD_A", "TRD_B"],
        "active_trades": [],
        "orphaned_trades": [],
    }
    s.update(over)
    return s


def _active(tid, ftr="SL_FIRST", last_quote=None):
    r = {"trade_id": tid, "first_touch_result": ftr}
    if last_quote:
        r["first_touch_state"] = {"last_valid_quote_time": last_quote}
    else:
        r["first_touch_state"] = {}
    return r


def test_classify_terminal_in_outcomes(tmp_path):
    _seed(tmp_path, "NIFTY",
          _base_state(active_trades=[_active("TRD_X")]),
          outcome_ids=["TRD_X"])
    st = rec.classify_market(str(tmp_path), "NIFTY")
    assert st[0]["classification"] == rec.TERMINAL_ALREADY_RECORDED


def test_classify_terminal_in_counted_ids(tmp_path):
    _seed(tmp_path, "NIFTY",
          _base_state(active_trades=[_active("TRD_A")]))
    st = rec.classify_market(str(tmp_path), "NIFTY")
    assert st[0]["classification"] == rec.TERMINAL_ALREADY_RECORDED


def test_classify_already_orphaned(tmp_path):
    state = _base_state(
        active_trades=[_active("TRD_O")],
        orphaned_trades=[{"trade_id": "TRD_O"}],
    )
    _seed(tmp_path, "NIFTY", state)
    st = rec.classify_market(str(tmp_path), "NIFTY")
    assert st[0]["classification"] == rec.STALE_RESTART_ORPHAN_PROVEN
    assert st[0]["reason"].startswith("ALREADY_ORPHANED")


def test_classify_uninitialized_first_touch_is_orphan(tmp_path):
    state = _base_state(active_trades=[_active("TRD_U", ftr="")])
    _seed(tmp_path, "NIFTY", state)
    st = rec.classify_market(str(tmp_path), "NIFTY")
    assert st[0]["classification"] == rec.STALE_RESTART_ORPHAN_PROVEN
    assert st[0]["reason"] == "FIRST_TOUCH_UNINITIALIZED"


def test_classify_stale_last_quote_is_orphan(tmp_path):
    now = datetime(2026, 9, 28, 20, 0, tzinfo=IST)
    old = (now - timedelta(hours=6)).isoformat()
    state = _base_state(active_trades=[_active("TRD_S", ftr="NONE", last_quote=old)])
    _seed(tmp_path, "NIFTY", state)
    st = rec.classify_market(str(tmp_path), "NIFTY", now=now)
    assert st[0]["classification"] == rec.STALE_RESTART_ORPHAN_PROVEN
    assert st[0]["reason"].startswith("LAST_QUOTE_STALE")


def test_classify_fresh_last_quote_is_unresolved(tmp_path):
    now = datetime(2026, 9, 28, 20, 0, tzinfo=IST)
    fresh = (now - timedelta(minutes=10)).isoformat()
    state = _base_state(active_trades=[_active("TRD_F", ftr="NONE", last_quote=fresh)])
    _seed(tmp_path, "NIFTY", state)
    st = rec.classify_market(str(tmp_path), "NIFTY", now=now)
    assert st[0]["classification"] == rec.UNRESOLVED_HOLD


def test_reconcile_dry_run_does_not_write(tmp_path):
    state = _base_state(active_trades=[_active("TRD_U", ftr="")])
    _seed(tmp_path, "NIFTY", state)
    before = _read_state(tmp_path, "NIFTY")
    rpt = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=False)
    after = _read_state(tmp_path, "NIFTY")
    assert before == after
    assert rpt["applied"] is False
    assert len(rpt["moved"]) == 1
    assert rpt["moved"][0]["trade_id"] == "TRD_U"


def test_reconcile_apply_moves_proven_orphan(tmp_path):
    state = _base_state(active_trades=[_active("TRD_U", ftr="")])
    _seed(tmp_path, "NIFTY", state)
    rpt = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    after = _read_state(tmp_path, "NIFTY")
    assert rpt["applied"] is True
    assert len(rpt["moved"]) == 1
    assert after["active_trades"] == []
    assert len(after["orphaned_trades"]) == 1
    o = after["orphaned_trades"][0]
    assert o["trade_id"] == "TRD_U"
    assert o["orphan_reason"] == "FIRST_TOUCH_UNINITIALIZED"
    assert o["source_state"] == "active_trades"
    assert o["reconciled_at"].startswith("2026-")


def test_reconcile_apply_preserves_counters(tmp_path):
    state = _base_state(
        active_trades=[_active("TRD_U", ftr="")],
        certification_counter=4,
        certification_wins=0,
        certification_losses=4,
        counted_trade_ids=["TRD_A", "TRD_B"],
    )
    _seed(tmp_path, "NIFTY", state)
    rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    after = _read_state(tmp_path, "NIFTY")
    assert after["certification_counter"] == 4
    assert after["certification_wins"] == 0
    assert after["certification_losses"] == 4
    assert after["counted_trade_ids"] == ["TRD_A", "TRD_B"]


def test_reconcile_apply_retains_terminal_and_holds_unresolved(tmp_path):
    now = datetime(2026, 9, 28, 20, 0, tzinfo=IST)
    fresh = (now - timedelta(minutes=5)).isoformat()
    state = _base_state(
        active_trades=[
            _active("TRD_A"),                                     # in counted_ids → TERMINAL
            _active("TRD_F", ftr="NONE", last_quote=fresh),       # fresh → UNRESOLVED
            _active("TRD_U", ftr=""),                             # uninitialized → ORPHAN
        ]
    )
    _seed(tmp_path, "NIFTY", state)
    rpt = rec.reconcile_market_state(
        str(tmp_path), "NIFTY", apply=True, now=now
    )
    after = _read_state(tmp_path, "NIFTY")
    tids_kept = [r["trade_id"] for r in after["active_trades"]]
    assert "TRD_A" in tids_kept
    assert "TRD_F" in tids_kept
    assert "TRD_U" not in tids_kept
    assert len(rpt["moved"]) == 1
    assert len(rpt["retained"]) == 1
    assert len(rpt["held"]) == 1


def test_reconcile_apply_idempotent(tmp_path):
    state = _base_state(active_trades=[_active("TRD_U", ftr="")])
    _seed(tmp_path, "NIFTY", state)
    rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    # Second run: nothing active, nothing moved
    rpt2 = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    assert rpt2["moved"] == []
    after = _read_state(tmp_path, "NIFTY")
    assert len(after["orphaned_trades"]) == 1


def test_reconcile_non_index_market_returns_empty(tmp_path):
    rpt = rec.reconcile_market_state(str(tmp_path), "CRUDEOILM", apply=True)
    assert rpt["skipped"] == "NON_INDEX_MARKET"
    assert rpt["moved"] == []


def test_reconcile_missing_state_returns_empty(tmp_path):
    rpt = rec.reconcile_market_state(str(tmp_path), "NIFTY", apply=True)
    assert rpt["skipped"] == "NO_STATE"
    assert rpt["moved"] == []


def test_classify_active_record_without_trade_id(tmp_path):
    state = _base_state(active_trades=[{"first_touch_result": "SL_FIRST"}])
    _seed(tmp_path, "NIFTY", state)
    st = rec.classify_market(str(tmp_path), "NIFTY")
    assert st[0]["classification"] == rec.UNRESOLVED_HOLD
    assert st[0]["reason"] == "NO_TRADE_ID"
