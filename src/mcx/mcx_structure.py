"""MCX market structure — spec §11.
HH/HL/LH/LL classification + VWAP + breakout state from MTF candles.
Uses per-timeframe swing_high/swing_low computed in mcx_mtf.
"""
from datetime import datetime, time as dtime


def _classify_swings(swing_highs, swing_lows):
    """Classify recent swing sequence."""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "INSUFFICIENT"
    hi_trend = "HH" if swing_highs[-1] > swing_highs[-2] else "LH"
    lo_trend = "HL" if swing_lows[-1] > swing_lows[-2] else "LL"
    if hi_trend == "HH" and lo_trend == "HL":
        return "UPTREND"
    if hi_trend == "LH" and lo_trend == "LL":
        return "DOWNTREND"
    if hi_trend == "HH" and lo_trend == "LL":
        return "EXPANDING"
    if hi_trend == "LH" and lo_trend == "HL":
        return "CONTRACTING"
    return "MIXED"


def session_vwap(obj, token, exchange="MCX", now=None):
    """Compute VWAP from today's 5m candles. Returns dict or None."""
    if now is None:
        now = datetime.now()
    try:
        frm = now.strftime("%Y-%m-%d 09:00")
        to = now.strftime("%Y-%m-%d %H:%M")
        resp = obj.getCandleData({
            "exchange": exchange, "symboltoken": str(token),
            "interval": "FIVE_MINUTE", "fromdate": frm, "todate": to,
        })
    except Exception:
        return None
    if not resp or not resp.get("data"):
        return None
    try:
        total_pv = 0.0
        total_v = 0.0
        for row in resp["data"]:
            # [ts, o, h, l, c, v]
            h = float(row[2] or 0); l = float(row[3] or 0); c = float(row[4] or 0)
            v = float(row[5] or 0)
            typical = (h + l + c) / 3.0
            total_pv += typical * v
            total_v += v
        if total_v <= 0:
            return None
        vwap = total_pv / total_v
        return {"vwap": round(vwap, 2), "candles": len(resp["data"]),
                "total_volume": int(total_v)}
    except Exception:
        return None


def compute_structure(mtf, vwap_ctx, current_price):
    """Returns structure dict with per-TF state + overall."""
    if not mtf or mtf.get("status") != "OK":
        return {"status": "MTF_UNAVAILABLE"}

    tfs = mtf.get("timeframes", {})
    out = {"status": "OK", "timeframes": {}}

    for tf in ["5m", "15m", "30m", "1h"]:
        v = tfs.get(tf, {})
        if v.get("status") != "OK":
            out["timeframes"][tf] = {"state": "NODATA"}
            continue
        sh = v.get("swing_high")
        sl = v.get("swing_low")
        last = v.get("last_close")
        if sh and sl and last:
            # Where is price relative to swing band?
            rng = sh - sl if sh > sl else 1
            pos = (last - sl) / rng  # 0..1
            if pos > 0.8:   band = "NEAR_HIGH"
            elif pos < 0.2: band = "NEAR_LOW"
            else:           band = "MID"
            out["timeframes"][tf] = {
                "state": v.get("trend", "FLAT"),
                "swing_high": sh, "swing_low": sl,
                "position": band, "pos_pct": round(pos * 100, 1),
            }
        else:
            out["timeframes"][tf] = {"state": "PARTIAL"}

    # VWAP context
    if vwap_ctx and vwap_ctx.get("vwap") and current_price:
        v = vwap_ctx["vwap"]
        if current_price > v:
            out["vwap_position"] = "ABOVE"
            out["vwap_distance_pct"] = round((current_price - v) / v * 100, 3)
        elif current_price < v:
            out["vwap_position"] = "BELOW"
            out["vwap_distance_pct"] = round((v - current_price) / v * 100, 3)
        else:
            out["vwap_position"] = "AT"
        out["vwap"] = v
    else:
        out["vwap_position"] = "UNKNOWN"

    # Overall structure direction
    dirs = [out["timeframes"][tf].get("state") for tf in ["15m", "30m"]
            if out["timeframes"][tf].get("state") in ("UP", "DOWN")]
    if dirs.count("UP") == 2:
        out["overall_structure"] = "BULLISH"
    elif dirs.count("DOWN") == 2:
        out["overall_structure"] = "BEARISH"
    elif dirs.count("UP") == 1:
        out["overall_structure"] = "WEAK_BULLISH"
    elif dirs.count("DOWN") == 1:
        out["overall_structure"] = "WEAK_BEARISH"
    else:
        out["overall_structure"] = "MIXED"

    return out


def describe(s):
    if s.get("status") != "OK":
        return f"STRUCTURE: {s.get('status')}"
    lines = [f"STRUCTURE: {s.get('overall_structure')}  VWAP={s.get('vwap_position')}"
             f" ({s.get('vwap_distance_pct')}%)"]
    for tf, v in s.get("timeframes", {}).items():
        lines.append(f"  {tf}: {v.get('state')}  pos={v.get('position')} ({v.get('pos_pct')}%)")
    return "\n".join(lines)


if __name__ == "__main__":
    print("mcx_structure module loaded OK")
