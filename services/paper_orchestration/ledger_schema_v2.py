"""Ledger schema reader — Phase 11 of F15-R1.

Read-only. Pure functions. No state writes.

Reads the actual row schema produced by the index paper runtime:
  predictions:  data/paper_trades/{market_lower}_predictions.jsonl
  outcomes:     data/paper_trades/{market_lower}_outcomes.jsonl

Fields confirmed against 2026-09-28 live rows (see F15-R1 design):
  prediction: timestamp, market, action ("BUY_PUT"|"BUY_CALL"|"NO_TRADE"),
              readiness ("READY"|"BLOCKED"), blockers, selected_trade
  outcome:    trade_id, market, net_pnl, exit_reason,
              first_touch_result ("T1_FIRST"|"SL_FIRST"|"AMBIGUOUS"|"NONE"),
              certification_countable (bool), certification_win (bool),
              certification_loss (bool), certification_trade_date
"""
from __future__ import annotations

import json
from pathlib import Path

PREDICTION_ACTIONS_ENTRY = ("BUY_CALL", "BUY_PUT")
PREDICTION_ACTIONS_WAIT = ("NO_TRADE",)
FIRST_TOUCH_VALUES = ("T1_FIRST", "SL_FIRST", "AMBIGUOUS", "NONE")


MCX_MARKETS = ("CRUDEOILM", "GOLDM", "NATGASMINI")


def _ledger_path(repo_root, market, kind):
    m = market.upper()
    prefix = "mcx_" if m in MCX_MARKETS else ""
    return (
        Path(repo_root)
        / "data"
        / "paper_trades"
        / f"{prefix}{m.lower()}_{kind}.jsonl"
    )


def _read_jsonl(path):
    rows = []
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rows.append(json.loads(raw))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def read_predictions(repo_root, market):
    return _read_jsonl(_ledger_path(repo_root, market, "predictions"))


def read_outcomes(repo_root, market):
    return _read_jsonl(_ledger_path(repo_root, market, "outcomes"))


def rows_for_day(rows, day_iso):
    """Filter rows whose timestamp/entry_time starts with `day_iso` (YYYY-MM-DD)."""
    out = []
    for r in rows:
        for k in ("timestamp", "entry_time", "certification_trade_date"):
            v = r.get(k)
            if isinstance(v, str) and v.startswith(day_iso):
                out.append(r)
                break
    return out


def summarize_predictions(rows):
    entry = 0
    wait = 0
    other = 0
    for r in rows:
        a = r.get("action")
        if a in PREDICTION_ACTIONS_ENTRY:
            entry += 1
        elif a in PREDICTION_ACTIONS_WAIT:
            wait += 1
        else:
            other += 1
    return {
        "total": len(rows),
        "entry_actions": entry,
        "wait_actions": wait,
        "other_actions": other,
    }


def summarize_outcomes(rows):
    """Return a deterministic summary of an outcome-ledger slice."""
    n = len(rows)
    econ_wins = 0
    econ_losses = 0
    net_pnl_sum = 0.0
    cert_countable = 0
    cert_wins = 0
    cert_losses = 0
    ftc = {v: 0 for v in FIRST_TOUCH_VALUES}
    ftc_other = 0
    ambiguous = 0

    for r in rows:
        pnl = r.get("net_pnl")
        if isinstance(pnl, (int, float)):
            net_pnl_sum += float(pnl)
            if pnl > 0:
                econ_wins += 1
            else:
                econ_losses += 1

        if r.get("certification_countable") is True:
            cert_countable += 1
        if r.get("certification_win") is True:
            cert_wins += 1
        if r.get("certification_loss") is True:
            cert_losses += 1
        if r.get("evidence_ambiguous") is True:
            ambiguous += 1

        ftr = r.get("first_touch_result")
        if ftr in ftc:
            ftc[ftr] += 1
        else:
            ftc_other += 1

    return {
        "total": n,
        "economic_wins": econ_wins,
        "economic_losses": econ_losses,
        "net_pnl": round(net_pnl_sum, 2),
        "certification_countable": cert_countable,
        "certification_wins": cert_wins,
        "certification_losses": cert_losses,
        "evidence_ambiguous": ambiguous,
        "first_touch_T1_FIRST": ftc["T1_FIRST"],
        "first_touch_SL_FIRST": ftc["SL_FIRST"],
        "first_touch_AMBIGUOUS": ftc["AMBIGUOUS"],
        "first_touch_NONE": ftc["NONE"],
        "first_touch_other": ftc_other,
    }
