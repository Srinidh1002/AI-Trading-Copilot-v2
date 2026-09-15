"""MCX external context — global benchmarks that drive commodities.
READ-ONLY. Uses yfinance (already installed). No broker calls.
"""
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False


# Per-product external driver map (blueprint §9.1-§9.3)
DRIVERS = {
    "CRUDEOILM": {
        "primary": [
            ("WTI", "CL=F", "US crude benchmark — MCX tracks NYMEX WTI"),
            ("Brent", "BZ=F", "Global crude benchmark"),
        ],
        "cross_asset": [
            ("USDINR", "USDINR=X", "INR translation of USD crude"),
            ("DXY", "DX-Y.NYB", "Dollar strength (inverse to commodities)"),
        ],
    },
    "GOLDM": {
        "primary": [
            ("Gold", "GC=F", "COMEX gold — MCX tracks global gold"),
        ],
        "cross_asset": [
            ("USDINR", "USDINR=X", "INR translation"),
            ("DXY", "DX-Y.NYB", "Dollar strength (inverse to gold)"),
            ("US10Y", "^TNX", "US 10Y yield (gold vs yield)"),
        ],
    },
    "NATGASMINI": {
        "primary": [
            ("NatGas", "NG=F", "Henry Hub natural gas"),
        ],
        "cross_asset": [
            ("USDINR", "USDINR=X", "INR translation"),
            ("Crude", "CL=F", "Energy complex correlation"),
        ],
    },
}


def _fetch_one(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.history(period="5d", interval="1h")
        if info is None or info.empty:
            return None
        closes = info["Close"].dropna()
        if len(closes) < 2:
            return None
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        change_1 = ((last - prev) / prev * 100) if prev else 0.0
        # 5d change
        if len(closes) >= 5:
            base = float(closes.iloc[0])
            change_5 = ((last - base) / base * 100) if base else 0.0
        else:
            change_5 = None
        return {
            "last": round(last, 4),
            "chg_1": round(change_1, 2),
            "chg_5": round(change_5, 2) if change_5 is not None else None,
            "samples": len(closes),
        }
    except Exception as e:
        return {"error": str(e)[:80]}


def _classify(change):
    if change is None:
        return "UNKNOWN"
    if change > 1.0:   return "STRONG_UP"
    if change > 0.3:   return "UP"
    if change > 0.1:   return "WEAK_UP"
    if change < -1.0:  return "STRONG_DOWN"
    if change < -0.3:  return "DOWN"
    if change < -0.1:  return "WEAK_DOWN"
    return "FLAT"


def fetch_context(product):
    if not YF_OK:
        return {"status": "YF_UNAVAILABLE"}
    spec = DRIVERS.get(product.upper())
    if not spec:
        return {"status": "NO_DRIVER_MAP"}

    out = {"status": "OK", "product": product.upper(),
           "primary": {}, "cross_asset": {}, "fetched_at": datetime.now().isoformat(timespec="seconds")}

    for label, symbol, note in spec["primary"]:
        d = _fetch_one(symbol)
        if d and "error" not in d:
            d["note"] = note
            d["regime"] = _classify(d["chg_1"])
            out["primary"][label] = d
        else:
            out["primary"][label] = {"error": (d or {}).get("error", "NO_DATA")}

    for label, symbol, note in spec["cross_asset"]:
        d = _fetch_one(symbol)
        if d and "error" not in d:
            d["note"] = note
            d["regime"] = _classify(d["chg_1"])
            out["cross_asset"][label] = d
        else:
            out["cross_asset"][label] = {"error": (d or {}).get("error", "NO_DATA")}

    # Simple composite crude direction (using primary only)
    primary_moves = [v["chg_1"] for v in out["primary"].values() if "chg_1" in v]
    if primary_moves:
        avg = sum(primary_moves) / len(primary_moves)
        out["composite_move_1d_pct"] = round(avg, 2)
        out["composite_regime"] = _classify(avg)
    else:
        out["composite_move_1d_pct"] = None
        out["composite_regime"] = "UNKNOWN"

    return out


def print_context(ctx):
    if ctx["status"] != "OK":
        print(f"  status={ctx['status']}")
        return
    print(f"\n{ctx['product']} — external context  ({ctx['fetched_at']})")
    print(f"  Composite 1d move: {ctx['composite_move_1d_pct']}%  regime={ctx['composite_regime']}")
    print(f"\n  --- Primary drivers ---")
    for label, d in ctx["primary"].items():
        if "error" in d:
            print(f"    {label:<10} ERROR: {d['error']}")
        else:
            print(f"    {label:<10} {d['last']:>12.4f}  "
                  f"1d={d['chg_1']:>+6.2f}%  5d={d['chg_5']:>+6.2f}%  "
                  f"regime={d['regime']:<12} {d['note']}")
    print(f"\n  --- Cross-asset ---")
    for label, d in ctx["cross_asset"].items():
        if "error" in d:
            print(f"    {label:<10} ERROR: {d['error']}")
        else:
            print(f"    {label:<10} {d['last']:>12.4f}  "
                  f"1d={d['chg_1']:>+6.2f}%  5d={d['chg_5']:>+6.2f}%  "
                  f"regime={d['regime']:<12} {d['note']}")


if __name__ == "__main__":
    print("=" * 100)
    print("MCX EXTERNAL CONTEXT — read only")
    print("=" * 100)
    for prod in ["CRUDEOILM", "GOLDM", "NATGASMINI"]:
        ctx = fetch_context(prod)
        print_context(ctx)
