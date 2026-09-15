"""Breaking-news market reaction — Section 6.19-6.21, 6.50.
Reuses Section-4 slice_windows. Verification and reaction are SEPARATE.
"""
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_macro_reaction import slice_windows, REACTION_WINDOWS

# Add 0-1m window for breaking news (Section 6.20)
BREAKING_WINDOWS = dict(REACTION_WINDOWS)
BREAKING_WINDOWS["R0"] = (0, 1)

PRODUCT_REACTION_SYMBOLS = {
    "CRUDEOILM": ["WTI", "BRENT"],
    "GOLDM": ["COMEX_GOLD", "DXY", "USDINR"],
    "NATGASMINI": ["HENRY_HUB"],
}

REACTION_STATES = ("CONFIRMED", "PARTIALLY_CONFIRMED", "CONFLICTED",
                   "INCONCLUSIVE", "DATA_UNAVAILABLE")


def direction_of_return(windows, key="R2"):
    """Determine UP/DOWN/MIXED from sliced windows."""
    w = windows.get(key, {})
    if w.get("status") != "OK":
        return "UNKNOWN"
    f, l = w.get("first"), w.get("last")
    if f is None or l is None:
        return "UNKNOWN"
    if l > f:
        return "UP"
    if l < f:
        return "DOWN"
    return "MIXED"


def classify_observed_reaction(theoretical_impact, observed_direction):
    """Section 6.21 — same classifier as Section 4 for consistency."""
    if theoretical_impact in ("MIXED", "UNCERTAIN") or observed_direction in ("UNKNOWN", "MIXED"):
        return "INCONCLUSIVE"
    if (theoretical_impact == "BULLISH" and observed_direction == "UP") or \
       (theoretical_impact == "BEARISH" and observed_direction == "DOWN"):
        return "CONFIRMED"
    return "CONFLICTED"


def build_reaction_report(event, observations_by_symbol):
    """Return per-symbol windows + overall classification. Deterministic."""
    event_time = event.get("occurrence_time") or event.get("source_published_at")
    out = {"symbols": {}}
    from datetime import datetime
    try:
        ev_dt = datetime.fromisoformat(event_time) if event_time != "UNKNOWN" else None
    except Exception:
        ev_dt = None
    if ev_dt is None:
        out["overall_reaction"] = "DATA_UNAVAILABLE"
        return out
    for sym, obs in (observations_by_symbol or {}).items():
        w = slice_windows(ev_dt, obs)
        out["symbols"][sym] = w
    overall_dirs = []
    for sym, w in out["symbols"].items():
        d = direction_of_return(w, "R2")
        out["symbols"][sym]["direction"] = d
        overall_dirs.append(d)
    if not overall_dirs:
        out["overall_reaction"] = "DATA_UNAVAILABLE"
    else:
        out["overall_reaction"] = classify_observed_reaction(
            event.get("theoretical_impact"), overall_dirs[0])
    return out


if __name__ == "__main__":
    print("mcx_breaking_reaction module loaded OK")
    print("BREAKING_WINDOWS:", list(BREAKING_WINDOWS.keys()))
