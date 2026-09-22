"""Post-close analysis for one market.

Reads the day's predictions, outcomes, and state; writes a markdown report.
Never changes strategy version, thresholds, SL, targets, or counters.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path


def _iter_jsonl(path: Path):
    if not path.is_file():
        return
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def analyze_market_day(*, market: str, day: date, repo_root: str) -> dict:
    root = Path(repo_root)
    lower = market.lower()

    if market in ("NIFTY", "SENSEX"):
        pred = root / f"data/paper_trades/{lower}_predictions.jsonl"
        outc = root / f"data/paper_trades/{lower}_outcomes.jsonl"
        state = root / f"data/paper_trades/{lower}_experimental.json"
    else:
        pred = root / f"data/paper_trades/mcx_{lower}_predictions.jsonl"
        outc = root / f"data/paper_trades/mcx_{lower}_outcomes.jsonl"
        state = root / f"data/paper_trades/mcx_{lower}_experimental.json"

    day_str = day.isoformat()

    decisions_today = 0
    decision_actions = Counter()
    wait_reasons = Counter()
    entry_trades_today = 0
    for rec in _iter_jsonl(pred):
        ts = str(rec.get("timestamp") or rec.get("ts") or "")
        if not ts.startswith(day_str):
            continue
        decisions_today += 1
        action = str(rec.get("action") or rec.get("decision") or "").upper()
        if action:
            decision_actions[action] += 1
        reason = rec.get("reason") or rec.get("wait_reason")
        if reason:
            wait_reasons[str(reason)[:80]] += 1
        if action in ("CALL", "PUT"):
            entry_trades_today += 1

    outcomes_today = 0
    wins = 0
    losses = 0
    first_t1 = 0
    first_sl = 0
    net_pnl = 0.0
    for rec in _iter_jsonl(outc):
        ts = str(rec.get("closed_at") or rec.get("timestamp") or "")
        if not ts.startswith(day_str):
            continue
        outcomes_today += 1
        outcome = str(rec.get("outcome") or "").upper()
        if outcome in ("T1", "T1_FIRST", "T2", "T3", "WIN"):
            wins += 1
        elif outcome in ("SL", "SL_FIRST", "LOSS"):
            losses += 1
        if outcome == "T1_FIRST":
            first_t1 += 1
        elif outcome == "SL_FIRST":
            first_sl += 1
        pnl = rec.get("net_pnl") or rec.get("pnl") or 0.0
        try:
            net_pnl += float(pnl)
        except Exception:
            pass

    state_dict = {}
    if state.is_file():
        try:
            state_dict = json.loads(state.read_text(encoding="utf-8"))
        except Exception:
            state_dict = {}

    counter = state_dict.get("certification_counter")
    if counter is None:
        counter = state_dict.get("total_trades")
    epoch = state_dict.get("epoch") or state_dict.get("certification_epoch")

    return {
        "market": market,
        "day": day_str,
        "decisions_today": decisions_today,
        "decision_actions": dict(decision_actions),
        "wait_reasons_top": wait_reasons.most_common(5),
        "entry_trades_today": entry_trades_today,
        "outcomes_today": outcomes_today,
        "wins": wins,
        "losses": losses,
        "first_t1": first_t1,
        "first_sl": first_sl,
        "net_pnl": round(net_pnl, 2),
        "counter": counter,
        "epoch": epoch,
        "active_position": bool(state_dict.get("active_position")),
    }


def write_daily_report(summary: dict, *, repo_root: str) -> str:
    root = Path(repo_root)
    out_dir = root / "docs" / "daily_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    market = summary["market"]
    day = summary["day"]
    out_path = out_dir / f"{market}_{day}.md"

    lines = []
    lines.append(f"# {market} daily report - {day}")
    lines.append("")
    lines.append(f"- Epoch: `{summary.get('epoch')}`")
    lines.append(f"- Counter: `{summary.get('counter')}`")
    lines.append(f"- Active position at close: `{summary.get('active_position')}`")
    lines.append("")
    lines.append("## Decisions")
    lines.append(f"- Total decisions: {summary['decisions_today']}")
    lines.append(f"- Actions: {summary['decision_actions']}")
    lines.append("- Top WAIT reasons:")
    for reason, count in summary.get("wait_reasons_top") or []:
        lines.append(f"    - {reason} ({count})")
    lines.append("")
    lines.append("## Trades")
    lines.append(f"- Entries: {summary['entry_trades_today']}")
    lines.append(f"- Closed: {summary['outcomes_today']}")
    lines.append(f"- Wins: {summary['wins']}")
    lines.append(f"- Losses: {summary['losses']}")
    lines.append(f"- First touch T1: {summary['first_t1']}")
    lines.append(f"- First touch SL: {summary['first_sl']}")
    lines.append(f"- Net P&L: Rs {summary['net_pnl']}")
    lines.append("")
    lines.append("_Strategy version frozen for this epoch. No threshold change._")

    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return str(out_path)
