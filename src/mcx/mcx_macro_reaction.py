"""Reaction engine — Section 4.13, 4.14, 4.15 + historical mode.
Uses yfinance for historical windows around a specified event_time.
No fabrication. Honest reason codes.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

REACTION_CLASSES = ("CONFIRMED", "PARTIALLY_CONFIRMED", "CONFLICTED",
                    "INCONCLUSIVE", "DATA_UNAVAILABLE")

# Canonical failure reason codes (Section 4 close-out)
REASON_HISTORICAL_DATA_AVAILABLE = "HISTORICAL_DATA_AVAILABLE"
REASON_HISTORICAL_PROVIDER_UNAVAILABLE = "HISTORICAL_PROVIDER_UNAVAILABLE"
REASON_NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
REASON_SYMBOL_UNAVAILABLE = "SYMBOL_UNAVAILABLE"
REASON_INTERVAL_UNAVAILABLE = "INTERVAL_UNAVAILABLE"
REASON_INSUFFICIENT_PRE_EVENT_DATA = "INSUFFICIENT_PRE_EVENT_DATA"
REASON_INSUFFICIENT_POST_EVENT_DATA = "INSUFFICIENT_POST_EVENT_DATA"
REASON_REACTION_DATA_UNAVAILABLE = "REACTION_DATA_UNAVAILABLE"

REACTION_SYMBOLS = {
    "DXY": "DX-Y.NYB",
    "USDINR": "USDINR=X",
    "COMEX_GOLD": "GC=F",
    "WTI": "CL=F",
    "BRENT": "BZ=F",
    "HENRY_HUB": "NG=F",
    "US2Y": None,   # no reliable free source
    "US10Y": "^TNX",
    "SP500_FUT": "ES=F",
}

# Reaction windows (Section 4.14) — minutes relative to release
REACTION_WINDOWS = {
    "PRE":  (-15, -1),
    "R1":   (0, 5),
    "R2":   (5, 15),
    "R3":   (15, 30),
    "R4":   (30, 60),
}


def slice_windows(event_time_utc, observations):
    """Given tz-aware event time and a list of (ts_iso, price) observations,
    compute window-level metrics: pre-baseline, R1..R4 return.
    Observations must be tz-aware ISO strings with prices.
    """
    if event_time_utc.tzinfo is None:
        event_time_utc = event_time_utc.replace(tzinfo=timezone.utc)
    parsed = []
    for o in observations:
        try:
            ts = datetime.fromisoformat(o["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            parsed.append((ts, float(o["price"])))
        except Exception:
            continue
    parsed.sort(key=lambda x: x[0])
    out = {}
    for name, (m1, m2) in REACTION_WINDOWS.items():
        start = event_time_utc + timedelta(minutes=m1)
        end = event_time_utc + timedelta(minutes=m2)
        pts = [p for ts, p in parsed if start <= ts <= end]
        if not pts:
            out[name] = {"status": REASON_INSUFFICIENT_PRE_EVENT_DATA if m2 < 0 else REASON_INSUFFICIENT_POST_EVENT_DATA}
        else:
            out[name] = {
                "status": "OK",
                "first": round(pts[0], 4), "last": round(pts[-1], 4),
                "min": round(min(pts), 4), "max": round(max(pts), 4),
                "n": len(pts),
            }
    return out


def capture_reaction(symbol, event_time_utc, mode="HISTORICAL",
                     pre_minutes=20, post_minutes=70):
    """Fetch historical window around event_time_utc.
    event_time_utc must be a tz-aware datetime.
    mode: HISTORICAL (default) or LIVE
    """
    if not YF_OK:
        return {"symbol": symbol, "status": REASON_HISTORICAL_PROVIDER_UNAVAILABLE,
                "reason": "yfinance not installed", "mode": mode}
    yf_sym = REACTION_SYMBOLS.get(symbol)
    if not yf_sym:
        return {"symbol": symbol, "status": REASON_SYMBOL_UNAVAILABLE,
                "reason": f"no symbol mapping for {symbol}", "mode": mode}
    if event_time_utc is None:
        return {"symbol": symbol, "status": REASON_REACTION_DATA_UNAVAILABLE,
                "reason": "event_time_utc required"}
    if event_time_utc.tzinfo is None:
        event_time_utc = event_time_utc.replace(tzinfo=timezone.utc)

    start = event_time_utc - timedelta(minutes=pre_minutes + 5)
    end = event_time_utc + timedelta(minutes=post_minutes + 5)
    try:
        ticker = yf.Ticker(yf_sym)
        df = ticker.history(start=start, end=end, interval="1m")
        if df is None or df.empty:
            return {"symbol": symbol, "status": REASON_HISTORICAL_PROVIDER_UNAVAILABLE,
                    "reason": "provider returned no data for requested interval",
                    "mode": mode,
                    "requested_start": start.isoformat(),
                    "requested_end": end.isoformat(),
                    "provider": "yfinance"}
        return {"symbol": symbol, "status": REASON_HISTORICAL_DATA_AVAILABLE,
                "mode": mode, "provider": "yfinance",
                "requested_start": start.isoformat(),
                "requested_end": end.isoformat(),
                "rows": len(df),
                "first_ts": str(df.index[0]), "last_ts": str(df.index[-1])}
    except Exception as e:
        return {"symbol": symbol, "status": REASON_NETWORK_UNAVAILABLE,
                "reason": str(e)[:100], "mode": mode}


def classify_reaction(theoretical_direction, observed_direction):
    """CONFIRMED / CONFLICTED / INCONCLUSIVE."""
    if theoretical_direction in ("MIXED", "UNKNOWN") or observed_direction in ("MIXED", "UNKNOWN"):
        return "INCONCLUSIVE"
    if theoretical_direction == observed_direction:
        return "CONFIRMED"
    if theoretical_direction in ("UP", "DOWN") and observed_direction in ("UP", "DOWN"):
        return "CONFLICTED"
    return "INCONCLUSIVE"


if __name__ == "__main__":
    print("mcx_macro_reaction module loaded OK")
    print("yfinance available:", YF_OK)
    # Historical smoke (won't run in tests)
    from datetime import datetime, timezone
    # 2026-09-11 18:00 IST = 12:30 UTC
    ev = datetime(2026, 9, 11, 12, 30, tzinfo=timezone.utc)
    for sym in ("DXY", "COMEX_GOLD", "WTI"):
        r = capture_reaction(sym, ev, mode="HISTORICAL")
        print(f"  {sym}: {r.get('status')} {r.get('reason','')[:60]}")
