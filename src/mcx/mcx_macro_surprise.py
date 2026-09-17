"""Surprise engine — Section 4.6, 4.5.
Pure math. No I/O. No fabrication.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_macro_models import (
    SURPRISE_SMALL_PP, SURPRISE_MODERATE_PP, SURPRISE_CLASSES,
)


def validate_consensus_timestamp(consensus_ts_iso, release_ts_iso):
    """Return (ok, reason). Post-release consensus is a violation."""
    if consensus_ts_iso is None:
        return False, "CONSENSUS_TS_MISSING"
    try:
        from datetime import datetime
        c = datetime.fromisoformat(consensus_ts_iso)
        r = datetime.fromisoformat(release_ts_iso)
    except Exception:
        return False, "CONSENSUS_TS_PARSE_FAILURE"
    if c >= r:
        return False, "CONSENSUS_TIME_TRAVEL_VIOLATION"
    return True, "OK"


def classify_surprise(actual, consensus, small=SURPRISE_SMALL_PP,
                      moderate=SURPRISE_MODERATE_PP, metric_id=None):
    """Return (classification, delta, reason)."""
    if consensus is None:
        return "CONSENSUS_UNAVAILABLE", None, "no consensus configured"
    if actual is None:
        return "CONSENSUS_UNAVAILABLE", None, "actual not yet released"
    try:
        delta = float(actual) - float(consensus)
    except Exception:
        return "CONSENSUS_UNAVAILABLE", None, "parse failure"
    abs_d = abs(delta)
    if abs_d < small:
        cls = "INLINE"
    elif abs_d < moderate:
        cls = "MODERATE_UPSIDE_SURPRISE" if delta > 0 else "MODERATE_DOWNSIDE_SURPRISE"
    else:
        cls = "LARGE_UPSIDE_SURPRISE" if delta > 0 else "LARGE_DOWNSIDE_SURPRISE"
    return cls, round(delta, 4), f"small={small} moderate={moderate}"


def enrich_event(event):
    """Given a canonical event, compute surprise classification per metric.
    Mutates a copy. Never fabricates.
    """
    out = dict(event)
    metrics = []
    for m in event.get("metrics", []):
        m2 = dict(m)
        cls, delta, reason = classify_surprise(m.get("actual"), m.get("consensus"),
                                               metric_id=m.get("metric_id"))
        m2["surprise_classification"] = cls
        m2["surprise_delta"] = delta
        m2["surprise_reason"] = reason
        metrics.append(m2)
    out["metrics"] = metrics
    return out


if __name__ == "__main__":
    print(classify_surprise(None, 3.1))
    print(classify_surprise(3.35, 3.1))
    print(classify_surprise(3.6, 3.1))
    print(classify_surprise(2.9, 3.1))
