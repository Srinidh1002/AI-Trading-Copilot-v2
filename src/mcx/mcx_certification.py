"""MCX certification — spec: T1-hit wins ≥80/100.
Tracks T1_HIT_WINS vs SL_LOSSES per epoch. Also diversity check.
"""
import json
import os
from datetime import datetime


CERTIFICATION_THRESHOLD = 80
DIVERSITY_MIN_DAYS = 5
DIVERSITY_MIN_REGIMES = 2
DIVERSITY_MIN_PHASES = 2
DIVERSITY_MAX_PER_DAY = 40


def classify_win(trade):
    """Return 'T1_WIN' | 'SL_LOSS' | 'NONCOUNTABLE' from authoritative
    first-touch evidence.

    exit_reason prefix and net_pnl sign are NOT certification authorities;
    they describe realized P&L, which is orthogonal to certification.
    """
    ft = (trade.get("first_touch_result") or "").upper()
    if ft == "T1_FIRST":
        return "T1_WIN"
    if ft == "SL_FIRST":
        return "SL_LOSS"
    return "NONCOUNTABLE"


def countable_total(state):
    """Authoritative fixed-sample certification denominator."""
    return (
        int(state.get("t1_hit_wins", 0) or 0)
        + int(state.get("sl_losses", 0) or 0)
    )


def _counted_completed_trades(state):
    """Return only completed trades accepted into certification."""
    counted = set(
        state.get("_counted_trade_ids", [])
    )

    return [
        trade
        for trade in state.get(
            "completed_trades",
            [],
        )
        if trade.get("trade_id") in counted
    ]


def _entry_day(trade):
    return str(
        trade.get("entry_time") or ""
    )[:10]


def update_counters(state, trade):
    """Mutate certification counters exactly once per accepted trade.

    Authority:
    - first-touch resolved trades only;
    - exactly the first 100 accepted countable trades;
    - maximum 40 accepted countable trades per entry date;
    - trade 101+ cannot alter the fixed sample.
    """
    tid = trade.get("trade_id")

    if not tid:
        return state

    seen = state.setdefault(
        "_counted_trade_ids",
        [],
    )

    rejected = state.setdefault(
        "_cert_rejected_trade_ids",
        [],
    )

    if tid in seen or tid in rejected:
        return state

    # Registry authority remains mandatory.
    from mcx.mcx_version import (
        is_certification_eligible,
    )

    product = (
        trade.get("product")
        or state.get("product")
    )

    if not is_certification_eligible(
        product
    ):
        trade["_counter_rejected"] = (
            "PRODUCT_NOT_CERTIFICATION_ELIGIBLE"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state

    if not bool(
        trade.get(
            "certification_eligible",
            False,
        )
    ):
        trade["_counter_rejected"] = (
            "RECORD_NOT_CERTIFICATION_ELIGIBLE"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state


    # First-touch remains the outcome authority.
    cls = classify_win(trade)

    if cls == "NONCOUNTABLE":

        trade[
            "_cert_noncountable_reason"
        ] = (
            "FIRST_TOUCH_MISSING_OR_AMBIGUOUS"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state


    # Fixed first-100 authority.
    #
    # Once 100 countable trades have been accepted,
    # no later trade can repair or change the epoch.
    if len(seen) >= 100:

        trade["_counter_rejected"] = (
            "CERTIFICATION_FIRST_100_COMPLETE"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state


    # Daily diversity authority must be enforced at
    # counting time, not merely evaluated afterward.
    entry_day = _entry_day(trade)

    if not entry_day:

        trade["_counter_rejected"] = (
            "ENTRY_DATE_MISSING_FOR_DAILY_CAP"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state


    same_day_count = sum(
        1
        for prior
        in _counted_completed_trades(
            state
        )
        if _entry_day(prior)
        == entry_day
    )


    if same_day_count >= DIVERSITY_MAX_PER_DAY:

        trade["_counter_rejected"] = (
            "DAILY_COUNTABLE_CAP_REACHED"
        )

        rejected.append(tid)

        state[
            "_cert_rejected_trade_ids"
        ] = rejected[-500:]

        return state


    state.setdefault(
        "t1_hit_wins",
        0,
    )

    state.setdefault(
        "sl_losses",
        0,
    )


    if cls == "T1_WIN":
        state["t1_hit_wins"] += 1

    elif cls == "SL_LOSS":
        state["sl_losses"] += 1

    else:
        raise AssertionError(
            f"unexpected certification class: {cls}"
        )


    seen.append(tid)

    state[
        "_counted_trade_ids"
    ] = seen[-500:]

    state[
        "_cert_rejected_trade_ids"
    ] = rejected[-500:]

    return state


def evaluate_diversity(state):
    """Return (passes: bool, details: dict)."""
    trades = _counted_completed_trades(state)
    days = set()
    regimes = set()
    phases = set()
    per_day = {}

    for t in trades:
        ts = (t.get("entry_time") or "")[:10]
        if ts:
            days.add(ts)
            per_day[ts] = per_day.get(ts, 0) + 1
        r = t.get("regime_at_entry")
        if r:
            regimes.add(r)
        hh = (t.get("entry_time") or "")[11:13]
        if hh:
            try:
                h = int(hh)
                phases.add("MORNING" if h < 17 else "EVENING")
            except Exception:
                pass

    details = {
        "distinct_days": len(days),
        "distinct_regimes": len(regimes),
        "distinct_phases": len(phases),
        "max_per_day": max(per_day.values()) if per_day else 0,
    }
    passes = (
        len(days) >= DIVERSITY_MIN_DAYS
        and len(regimes) >= DIVERSITY_MIN_REGIMES
        and len(phases) >= DIVERSITY_MIN_PHASES
        and (max(per_day.values()) if per_day else 0) <= DIVERSITY_MAX_PER_DAY
    )
    return passes, details


def status(state):
    """Return certification status dict."""
    t1 = state.get("t1_hit_wins", 0)
    sl = state.get("sl_losses", 0)
    total = countable_total(state)  # fixed certification denominator
    passes = t1 >= CERTIFICATION_THRESHOLD and total == 100
    div_pass, div_details = evaluate_diversity(state)
    return {
        "epoch": state.get("epoch"),
        "total_countable_trades": total,
        "t1_hit_wins": t1,
        "sl_losses": sl,
        "pass_requirement": f"T1_HIT_WINS >= {CERTIFICATION_THRESHOLD}/100",
        "passes_threshold": passes,
        "diversity_pass": div_pass,
        "diversity_details": div_details,
        "final_verdict": "PASS" if (passes and div_pass) else "NOT_YET",
    }


def print_status(state):
    s = status(state)
    print("=" * 70)
    print(f"MCX CERTIFICATION — {s['epoch']}")
    print("=" * 70)
    print(f"COUNTABLE PAPER TRADES     {s['total_countable_trades']} / 100")
    print(f"T1-HIT WINS                {s['t1_hit_wins']}")
    print(f"SL LOSSES                  {s['sl_losses']}")
    print()
    print(f"PASS REQUIREMENT:          {s['pass_requirement']}")
    print(f"THRESHOLD PASS:            {s['passes_threshold']}")
    print(f"DIVERSITY PASS:            {s['diversity_pass']}")
    print(f"DIVERSITY DETAILS:         {s['diversity_details']}")
    print(f"FINAL VERDICT:             {s['final_verdict']}")
    print("=" * 70)


if __name__ == "__main__":
    print("mcx_certification module loaded OK")
