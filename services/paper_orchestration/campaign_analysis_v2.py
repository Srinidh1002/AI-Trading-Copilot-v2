"""Post-close analysis for one market.

Reads the day's predictions, outcomes, and state; writes a markdown report.
Never changes strategy version, thresholds, SL, targets, or counters.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from services.paper_orchestration import ledger_schema_v2 as ledger  # noqa: E402


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
        state = root / f"data/paper_trades/{lower}_experimental.json"
    else:
        state = root / f"data/paper_trades/mcx_{lower}_experimental.json"

    day_str = day.isoformat()

    pred_rows_day = ledger.rows_for_day(
        ledger.read_predictions(repo_root, market), day_str
    )
    out_rows_day = ledger.rows_for_day(
        ledger.read_outcomes(repo_root, market), day_str
    )

    pred_summary = ledger.summarize_predictions(pred_rows_day)
    out_summary = ledger.summarize_outcomes(out_rows_day)

    decision_actions = Counter()
    wait_reasons = Counter()
    for rec in pred_rows_day:
        action = str(rec.get("action") or rec.get("decision") or "").upper()
        if action:
            decision_actions[action] += 1
        for b in rec.get("blockers") or []:
            wait_reasons[str(b)[:80]] += 1
        reason = rec.get("reason") or rec.get("wait_reason")
        if reason:
            wait_reasons[str(reason)[:80]] += 1

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

    # Index state uses active_trades (list); MCX uses active_position (dict).
    active_list = state_dict.get("active_trades")
    active_pos = state_dict.get("active_position")
    if isinstance(active_list, list) and active_list:
        active_bool = True
        active_count = len(active_list)
    elif isinstance(active_pos, dict) and active_pos.get("trade_id"):
        active_bool = True
        active_count = 1
    else:
        active_bool = False
        active_count = 0

    return {
        "market": market,
        "day": day_str,
        "decisions_today": pred_summary["total"],
        "decision_actions": dict(decision_actions),
        "wait_reasons_top": wait_reasons.most_common(5),
        "entry_trades_today": pred_summary["entry_actions"],
        "wait_actions": pred_summary["wait_actions"],
        "other_actions": pred_summary["other_actions"],
        "outcomes_today": out_summary["total"],
        "wins": out_summary["economic_wins"],
        "losses": out_summary["economic_losses"],
        "first_t1": out_summary["first_touch_T1_FIRST"],
        "first_sl": out_summary["first_touch_SL_FIRST"],
        "first_ambiguous": out_summary["first_touch_AMBIGUOUS"],
        "first_none": out_summary["first_touch_NONE"],
        "net_pnl": out_summary["net_pnl"],
        "certification_countable": out_summary["certification_countable"],
        "certification_wins": out_summary["certification_wins"],
        "certification_losses": out_summary["certification_losses"],
        "evidence_ambiguous": out_summary["evidence_ambiguous"],
        "counter": counter,
        "epoch": epoch,
        "active_position": active_bool,
        "active_position_count": active_count,
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
    lines.append(
        f"- Active position at close: `{summary.get('active_position')}` "
        f"(count={summary.get('active_position_count', 0)})"
    )
    lines.append("")
    lines.append("## Decisions")
    lines.append(f"- Total decisions: {summary['decisions_today']}")
    lines.append(
        f"- Entry actions (BUY_CALL/BUY_PUT): {summary['entry_trades_today']}"
    )
    lines.append(f"- WAIT/NO_TRADE actions: {summary.get('wait_actions', 0)}")
    lines.append(f"- Action histogram: {summary['decision_actions']}")
    lines.append("- Top WAIT reasons:")
    for reason, count in summary.get("wait_reasons_top") or []:
        lines.append(f"    - {reason} ({count})")
    lines.append("")
    lines.append("## Trades")
    lines.append(f"- Raw closed outcomes: {summary['outcomes_today']}")
    lines.append("")
    lines.append("### Economic outcome")
    lines.append(f"- Economic wins: {summary['wins']}")
    lines.append(f"- Economic losses: {summary['losses']}")
    lines.append(f"- Net P&L: Rs {summary['net_pnl']}")
    lines.append("")
    lines.append("### Certification outcome")
    lines.append(
        f"- Certification countable: {summary.get('certification_countable', 0)}"
    )
    lines.append(
        f"- Certification wins: {summary.get('certification_wins', 0)}"
    )
    lines.append(
        f"- Certification losses: {summary.get('certification_losses', 0)}"
    )
    lines.append("")
    lines.append("### First-touch histogram")
    lines.append(f"- T1_FIRST: {summary['first_t1']}")
    lines.append(f"- SL_FIRST: {summary['first_sl']}")
    lines.append(f"- AMBIGUOUS: {summary.get('first_ambiguous', 0)}")
    lines.append(f"- NONE: {summary.get('first_none', 0)}")
    lines.append(
        f"- Monitoring-gap ambiguity: {summary.get('evidence_ambiguous', 0)}"
    )
    lines.append("")
    lines.append("_Strategy version frozen for this epoch. No threshold change._")

    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return str(out_path)
