"""MCX regime classifier (blueprint §11, spec §8).
Inputs: MTF indicator dict from mcx_mtf.py + optional chain/vwap context.
Output: regime label + confidence + evidence.
Read-only. No trades.
"""


def _trend_score(timeframes):
    """Count directional alignment across timeframes weighted by timeframe."""
    weights = {"1m": 0.5, "5m": 1.0, "15m": 1.5, "30m": 1.5, "1h": 2.0}
    bull = 0.0
    bear = 0.0
    total_w = 0.0
    for tf, w in weights.items():
        v = timeframes.get(tf)
        if not v or v.get("status") != "OK":
            continue
        total_w += w
        d = v.get("trend", "FLAT")
        if d == "UP":
            bull += w
        elif d == "DOWN":
            bear += w
    if total_w == 0:
        return "NONE", 0.0, 0.0
    return ("UP" if bull > bear else "DOWN" if bear > bull else "FLAT",
            bull / total_w, bear / total_w)


def _volatility_state(timeframes):
    """Classify ATR relative to recent baseline. Returns LOW/NORMAL/HIGH/EXTREME."""
    atrs = [v.get("atr") for v in timeframes.values()
            if v.get("status") == "OK" and v.get("atr")]
    atrs = [a for a in atrs if a and a > 0]
    if len(atrs) < 2:
        return "UNKNOWN", 0.0
    avg = sum(atrs) / len(atrs)
    if avg <= 0:
        return "UNKNOWN", 0.0
    # Normalize: high if ATR > 1.5x median across TFs (rough proxy for "hot")
    atrs_sorted = sorted(atrs)
    median = atrs_sorted[len(atrs) // 2]
    ratio = avg / median if median else 0
    if ratio >= 2.0:
        return "EXTREME", ratio
    if ratio >= 1.3:
        return "HIGH", ratio
    if ratio <= 0.6:
        return "LOW", ratio
    return "NORMAL", ratio


def _structure_state(timeframes):
    """Detect compression vs expansion using 5m/15m candles if available."""
    tf5 = timeframes.get("5m", {})
    tf15 = timeframes.get("15m", {})
    # simple heuristic: ADX + ema separation
    adx = None
    for tf in (tf15, tf5):
        if tf.get("status") == "OK" and tf.get("adx") is not None:
            adx = tf["adx"]
            break
    if adx is None:
        return "UNKNOWN", 0.0
    if adx >= 30:
        return "EXPANSION", adx
    if adx <= 18:
        return "COMPRESSION", adx
    return "NEUTRAL", adx


def classify(timeframes, chain=None, vwap_ctx=None):
    """Returns dict: regime, confidence, evidence."""
    if not timeframes or not any(v.get("status") == "OK" for v in timeframes.values()):
        return {"regime": "EVIDENCE_UNAVAILABLE", "confidence": 0.0, "evidence": {}}

    dir_label, bull_w, bear_w = _trend_score(timeframes)
    vol_state, vol_ratio = _volatility_state(timeframes)
    struct_state, adx_val = _structure_state(timeframes)

    ev = {
        "direction": dir_label,
        "bull_weight": round(bull_w, 3),
        "bear_weight": round(bear_w, 3),
        "volatility": vol_state,
        "vol_ratio": round(vol_ratio, 3),
        "structure": struct_state,
        "adx": adx_val,
    }

    # Dislocated: extreme volatility + no direction
    if vol_state == "EXTREME" and dir_label == "FLAT":
        return {"regime": "DISLOCATED", "confidence": 0.85, "evidence": ev}

    # High volatility without trend
    if vol_state in ("HIGH", "EXTREME") and dir_label == "FLAT":
        return {"regime": "HIGH_VOLATILITY", "confidence": 0.7, "evidence": ev}

    # Low volatility compression
    if vol_state == "LOW" and struct_state == "COMPRESSION":
        return {"regime": "LOW_VOLATILITY", "confidence": 0.6, "evidence": ev}

    # Trend detection: strong directional weight + expansion
    if dir_label == "UP" and bull_w >= 0.6 and struct_state == "EXPANSION":
        conf = min(1.0, 0.5 + bull_w * 0.4)
        return {"regime": "TREND_UP", "confidence": round(conf, 2), "evidence": ev}
    if dir_label == "DOWN" and bear_w >= 0.6 and struct_state == "EXPANSION":
        conf = min(1.0, 0.5 + bear_w * 0.4)
        return {"regime": "TREND_DOWN", "confidence": round(conf, 2), "evidence": ev}

    # Breakout: strong on short timeframes but no 1h confirmation yet
    tf5 = timeframes.get("5m", {})
    if tf5.get("status") == "OK" and tf5.get("adx", 0) >= 25:
        if bull_w >= 0.55 and bear_w <= 0.15:
            return {"regime": "BREAKOUT_UP", "confidence": 0.6, "evidence": ev}
        if bear_w >= 0.55 and bull_w <= 0.15:
            return {"regime": "BREAKOUT_DOWN", "confidence": 0.6, "evidence": ev}

    # Default: RANGE — compute confidence from evidence strength
    # Higher confidence when: ADX weak, direction ambiguous, structure neutral
    adx_score = 0.5
    if adx_val is not None:
        # ADX 15 -> high confidence RANGE; ADX 25 -> low confidence RANGE
        if adx_val <= 15:   adx_score = 0.85
        elif adx_val <= 20: adx_score = 0.65
        elif adx_val <= 25: adx_score = 0.45
        else:               adx_score = 0.25

    # Directional clarity penalty: RANGE confidence drops if one side dominates
    dir_clarity = abs(bull_w - bear_w)   # 0..1
    dir_penalty = dir_clarity * 0.3      # up to -0.3

    range_conf = max(0.3, min(0.9, adx_score - dir_penalty))
    ev["range_conf_components"] = {
        "adx_score": round(adx_score, 2),
        "dir_clarity": round(dir_clarity, 3),
        "dir_penalty": round(dir_penalty, 3),
    }
    return {"regime": "RANGE", "confidence": round(range_conf, 2), "evidence": ev}


def describe(regime_dict):
    r = regime_dict
    ev = r.get("evidence", {})
    return (f"{r['regime']} (conf={r['confidence']})  "
            f"dir={ev.get('direction')}  vol={ev.get('volatility')}({ev.get('vol_ratio')})  "
            f"struct={ev.get('structure')}  adx={ev.get('adx')}")


if __name__ == "__main__":
    # Quick self-test with synthetic input
    fake = {
        "5m":  {"status": "OK", "trend": "UP",   "adx": 32, "atr": 25},
        "15m": {"status": "OK", "trend": "UP",   "adx": 30, "atr": 40},
        "1h":  {"status": "OK", "trend": "UP",   "adx": 28, "atr": 90},
    }
    r = classify(fake)
    print(describe(r))
