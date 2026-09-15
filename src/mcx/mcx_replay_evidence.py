"""Replay evidence — time-travel guard + Level A/B/C determination.
Never substitutes missing historical evidence with current or synthetic values.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class TimeTravelViolation(Exception):
    pass


class LiveDataBoundaryViolation(Exception):
    pass


def assert_not_future(evidence_ts, replay_time, label=""):
    """Raise if evidence timestamp is after replay time. Both must be tz-aware or both naive."""
    if evidence_ts is None:
        return
    if isinstance(evidence_ts, str):
        try:
            evidence_ts = datetime.fromisoformat(evidence_ts)
        except Exception:
            return
    if replay_time is None:
        return
    # Normalize tz
    if isinstance(evidence_ts, datetime) and evidence_ts.tzinfo is None and replay_time.tzinfo is not None:
        evidence_ts = evidence_ts.replace(tzinfo=replay_time.tzinfo)
    if isinstance(replay_time, datetime) and replay_time.tzinfo is None and evidence_ts.tzinfo is not None:
        replay_time = replay_time.replace(tzinfo=evidence_ts.tzinfo)
    if evidence_ts > replay_time:
        raise TimeTravelViolation(
            f"REPLAY_TIME_TRAVEL_VIOLATION [{label}]: "
            f"evidence_ts={evidence_ts.isoformat()} > replay_time={replay_time.isoformat()}"
        )


def filter_candles_by_replay_time(candles, replay_time, interval_seconds):
    """Return only candles whose CLOSE timestamp <= replay_time.
    Accepts candle timestamps interpreted as open time; close = open + interval.
    """
    from datetime import timedelta
    if not candles:
        return []
    out = []
    for c in candles:
        ts = c.get("timestamp") if isinstance(c, dict) else None
        if ts is None:
            continue
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                continue
        close_ts = ts + timedelta(seconds=interval_seconds)
        if close_ts <= replay_time:
            out.append(c)
    return out


def classify_ltp_comparison(recorded_ltp, candle):
    """Compare recorded LTP against nearest closed candle. Honest classification."""
    if not candle or recorded_ltp is None:
        return {"class": "NOT_COMPARABLE", "detail": "missing_input"}
    o = float(candle.get("open", 0))
    h = float(candle.get("high", 0))
    l = float(candle.get("low", 0))
    c = float(candle.get("close", 0))
    if c == recorded_ltp:
        cls = "EXACT_CLOSE_MATCH"
    elif l <= recorded_ltp <= h:
        cls = "WITHIN_CANDLE_RANGE"
    else:
        cls = "NEAREST_CLOSED_CANDLE_DIFFERENCE"
    return {
        "class": cls,
        "candle_open": o, "candle_high": h, "candle_low": l, "candle_close": c,
        "recorded_ltp": recorded_ltp,
        "diff_close": round(c - recorded_ltp, 4),
    }


def strategy_version_comparison(record_version, current_version):
    """Classify whether a recorded decision is same-strategy-comparable."""
    if not record_version:
        return "STRATEGY_VERSION_UNKNOWN"
    if record_version == current_version:
        return "SAME_STRATEGY_COMPARISON"
    return "DIFFERENT_STRATEGY_REFERENCE_ONLY"


def determine_replay_levels(has_candles, has_chain, has_bidask):
    """Return dict: level_a, level_b, level_c, level_a_reason."""
    a = "PASS" if has_candles else "FAIL"
    b = "UNAVAILABLE" if not has_chain else "PASS"
    c = "UNAVAILABLE" if not has_bidask else "PASS"
    reason_a = "historical futures candles available" if has_candles else "no candles returned"
    return {"level_a": a, "level_b": b, "level_c": c, "level_a_reason": reason_a}


def full_decision_status(chain_ok, external_ok, event_ok):
    """Determine if a full production decision can be produced."""
    missing = []
    if not chain_ok:
        missing.append("option_chain")
    if not external_ok:
        missing.append("external_context")
    if not event_ok:
        missing.append("event_context")
    if missing:
        return "REPLAY_EVIDENCE_INCOMPLETE", missing
    return "COMPLETE", []


if __name__ == "__main__":
    print("mcx_replay_evidence module loaded OK")
