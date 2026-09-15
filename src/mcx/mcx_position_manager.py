"""MCX position management engine — spec §16, §17, §18, §19, §20, §21.
Answers: hold / reduce / trail / exit, separate from entry logic.

Rules implemented:
§16 Thesis tracking: original vs current
§17 Contradiction exit: MTF flips against position + high opposite confidence
§18 Profit protection ladder: +5% / +8% / +10% / +12%
§19 MFE/MAE (already in pos dict, read here)
§20 Peak drawdown exit: if peak >= X and drawdown from peak >= Y
§21 Time stop: if in-trade too long without progress
"""

# Profit protection ladder (spec §18)
PROFIT_PROTECTION = [
    # (min_peak_pct, min_floor_pct, label)
    (12.0, 8.0, "STRONG_LOCK"),
    (10.0, 6.0, "LOCK_10"),
    (8.0,  4.0, "LOCK_8"),
    (5.0,  1.0, "MOVE_TO_PROFIT"),
]

# Peak-drawdown exit (spec §20) — exit if peak reached and price gives back too much
PEAK_DRAWDOWN = [
    # (min_peak_pct, max_giveback_pct)
    (12.0, 4.0),
    (8.0,  3.0),
    (5.0,  2.5),
]

# Time stop (spec §21) — minutes in trade without meaningful progress
TIME_STOP_MINUTES = 45
TIME_STOP_MIN_PROGRESS_PCT = 3.0


def thesis_valid(direction, decision_now, regime_now):
    """Direction: 'CALL' or 'PUT'.
    Returns (valid: bool, reason: str).
    """
    action = decision_now.get("action", "WAIT")
    long_c = decision_now.get("LONG_CONFIDENCE", 0)
    short_c = decision_now.get("SHORT_CONFIDENCE", 0)

    if direction == "CALL":
        # Thesis invalid if PUT signal strong OR CALL confidence collapsed
        if action == "BUY_PUT" and short_c >= 70:
            return False, f"THESIS_INVALID_OPPOSITE_PUT(short={short_c})"
        if long_c < 30:
            return False, f"CALL_CONFIDENCE_COLLAPSED(long={long_c})"
        return True, "CALL_THESIS_OK"
    elif direction == "PUT":
        if action == "BUY_CALL" and long_c >= 70:
            return False, f"THESIS_INVALID_OPPOSITE_CALL(long={long_c})"
        if short_c < 30:
            return False, f"PUT_CONFIDENCE_COLLAPSED(short={short_c})"
        return True, "PUT_THESIS_OK"
    return True, "UNKNOWN"


def evaluate_exit(pos, current_ltp, decision_now, regime_now, minutes_in_trade):
    """Returns (should_exit: bool, reason: str, new_stop: float or None).

    pos: open position dict with entry, max_profit_pct, min_profit_pct, stop_loss, type
    current_ltp: current option LTP
    decision_now: latest decision dict from mcx_decision.compose
    regime_now: latest regime dict
    minutes_in_trade: elapsed minutes since entry
    """
    if not pos or current_ltp <= 0:
        return False, "NO_DATA", None

    entry = pos["entry"]
    pnl_pct = ((current_ltp - entry) / entry) * 100
    peak = pos.get("max_profit_pct", 0.0)
    trough = pos.get("min_profit_pct", 0.0)

    direction = "CALL" if pos.get("type") == "CE" else "PUT"

    # §17 Contradiction exit — thesis invalidated
    valid, reason = thesis_valid(direction, decision_now, regime_now)
    if not valid:
        # Require at least 2 minutes to avoid flip-flop
        if minutes_in_trade >= 2:
            return True, f"CONTRADICTION_EXIT:{reason}", None

    # §21 Time stop — too long without progress
    if minutes_in_trade >= TIME_STOP_MINUTES and peak < TIME_STOP_MIN_PROGRESS_PCT:
        return True, f"TIME_STOP_{minutes_in_trade}min_peak={peak:.1f}%", None

    # §20 Peak drawdown — reversal after meaningful peak
    for min_peak, max_giveback in PEAK_DRAWDOWN:
        if peak >= min_peak:
            giveback = peak - pnl_pct
            if giveback >= max_giveback:
                return True, f"PEAK_DRAWDOWN_peak={peak:.1f}%_now={pnl_pct:.1f}%", None

    # §18 Profit protection — move stop up as profit grows
    new_stop = None
    for min_peak, min_floor, label in PROFIT_PROTECTION:
        if peak >= min_peak and pnl_pct >= min_floor:
            # Advance stop to lock in at min_floor pct of entry
            proposed_stop = round(entry * (1 + min_floor / 100), 2)
            current_stop = pos.get("stop_loss", 0)
            if proposed_stop > current_stop:
                new_stop = proposed_stop
                # Update label
                pos["profit_lock_label"] = label
            break

    return False, "HOLD", new_stop


if __name__ == "__main__":
    # Self-test: peak +12% now +4% -> should trigger PEAK_DRAWDOWN
    pos = {"entry": 100.0, "type": "CE", "max_profit_pct": 12.0,
           "min_profit_pct": 0.0, "stop_loss": 92.0}
    d = {"action": "WAIT", "LONG_CONFIDENCE": 50, "SHORT_CONFIDENCE": 30}
    should_exit, reason, new_stop = evaluate_exit(pos, 104.0, d, {}, 30)
    print(f"Test 1 (peak 12%, now +4%): exit={should_exit} reason={reason}")

    # Self-test: thesis invalidated
    pos2 = {"entry": 100.0, "type": "CE", "max_profit_pct": 2.0,
            "min_profit_pct": -1.0, "stop_loss": 92.0}
    d2 = {"action": "BUY_PUT", "LONG_CONFIDENCE": 20, "SHORT_CONFIDENCE": 75}
    should_exit2, reason2, _ = evaluate_exit(pos2, 99.0, d2, {}, 10)
    print(f"Test 2 (thesis invalid): exit={should_exit2} reason={reason2}")
