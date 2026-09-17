"""MCX directional bias — combines chain, external, and MTF evidence.
Mirrors decision_composer.py logic but for MCX. READ-ONLY.
Does NOT trade. Returns a bias dict.
"""


def _chain_vote(chain):
    if not chain or chain.get("status") != "OK":
        return None, 0.0
    pcr = chain.get("pcr_oi")
    if pcr is None:
        return None, 0.0
    # Contrarian (same as NIFTY convention)
    if pcr > 1.3:    return "BULLISH", 1.0
    if pcr > 1.1:    return "WEAK_BULLISH", 0.5
    if pcr < 0.7:    return "BEARISH", 1.0
    if pcr < 0.9:    return "WEAK_BEARISH", 0.5
    return "NEUTRAL", 0.0


def _external_vote(ctx):
    if not ctx or ctx.get("status") != "OK":
        return None, 0.0
    regime = ctx.get("composite_regime")
    comp = ctx.get("composite_move_1d_pct")
    if regime == "STRONG_UP":   return "BULLISH", 1.0
    if regime == "UP":          return "BULLISH", 0.7
    if regime == "WEAK_UP":     return "WEAK_BULLISH", 0.4
    if regime == "STRONG_DOWN": return "BEARISH", 1.0
    if regime == "DOWN":        return "BEARISH", 0.7
    if regime == "WEAK_DOWN":   return "WEAK_BEARISH", 0.4
    return "NEUTRAL", 0.0


def _mtf_vote(mtf):
    if not mtf or mtf.get("status") != "OK":
        return None, 0.0
    agg = mtf.get("aggregate_trend")
    if agg == "BULLISH":      return "BULLISH", 1.0
    if agg == "WEAK_BULLISH": return "WEAK_BULLISH", 0.5
    if agg == "BEARISH":      return "BEARISH", 1.0
    if agg == "WEAK_BEARISH": return "WEAK_BEARISH", 0.5
    return "NEUTRAL", 0.0


def compose(chain, ctx, mtf):
    votes = {
        "chain":    _chain_vote(chain),
        "external": _external_vote(ctx),
        "mtf":      _mtf_vote(mtf),
    }

    bull = 0.0
    bear = 0.0
    pillars_bull = 0
    pillars_bear = 0
    detail = {}

    for name, (verdict, weight) in votes.items():
        detail[name] = {"verdict": verdict, "weight": weight}
        if verdict in ("BULLISH",):
            bull += weight
            pillars_bull += 1
        elif verdict == "WEAK_BULLISH":
            bull += weight * 0.7
            pillars_bull += 1
        elif verdict == "BEARISH":
            bear += weight
            pillars_bear += 1
        elif verdict == "WEAK_BEARISH":
            bear += weight * 0.7
            pillars_bear += 1

    # Simple bias rules
    if bull > bear * 1.5 and bull >= 1.0 and pillars_bull >= 2:
        bias = "BULLISH"
        conf = "STRONG" if bull >= 2.0 and pillars_bull >= 3 else "MODERATE"
        action = "BUY_CALL"
    elif bear > bull * 1.5 and bear >= 1.0 and pillars_bear >= 2:
        bias = "BEARISH"
        conf = "STRONG" if bear >= 2.0 and pillars_bear >= 3 else "MODERATE"
        action = "BUY_PUT"
    else:
        bias = "NEUTRAL"
        conf = "WEAK"
        action = "WAIT"

    return {
        "bias": bias,
        "confidence": conf,
        "action": action,
        "bull_score": round(bull, 2),
        "bear_score": round(bear, 2),
        "pillars_bull": pillars_bull,
        "pillars_bear": pillars_bear,
        "votes": detail,
    }


def print_bias(b):
    print(f"\nMCX BIAS: {b['bias']} ({b['confidence']})  → {b['action']}")
    print(f"  bull_score={b['bull_score']}  bear_score={b['bear_score']}  "
          f"pillars_bull={b['pillars_bull']}  pillars_bear={b['pillars_bear']}")
    for k, v in b["votes"].items():
        print(f"    {k:<10} {v['verdict']:<15} (weight={v['weight']})")
