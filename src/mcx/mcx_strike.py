"""MCX strike selection — pick best CE/PE given bias + chain. READ-ONLY."""


def _score_option(entry, atm_strike, bias):
    """Score 0-100. Higher = better candidate."""
    if not entry:
        return 0, ["NO_DATA"]
    ltp = entry.get("ltp", 0)
    oi = entry.get("oi", 0)
    vol = entry.get("vol", 0)
    strike = entry.get("strike", 0)
    if ltp <= 0:
        return 0, ["BAD_LTP"]

    score = 40.0
    reasons = []

    # Liquidity: OI wall bonus
    if oi >= 200000:  score += 25; reasons.append("DEEP_OI")
    elif oi >= 100000: score += 15; reasons.append("HIGH_OI")
    elif oi >= 50000:  score += 8; reasons.append("MED_OI")
    elif oi < 10000:   reasons.append("THIN_OI")

    # Volume
    if vol >= 150000:  score += 20; reasons.append("HIGH_VOL")
    elif vol >= 50000: score += 12; reasons.append("MED_VOL")
    elif vol >= 10000: score += 6;  reasons.append("LOW_VOL")
    else:              reasons.append("THIN_VOL")

    # Distance from ATM: prefer near-ATM
    if atm_strike:
        dist = abs(strike - atm_strike)
        if dist <= 50:    score += 15; reasons.append("ATM")
        elif dist <= 100: score += 10; reasons.append("NEAR_ATM")
        elif dist <= 200: score += 4;  reasons.append("OTM")
        else: reasons.append("FAR_OTM")

    return min(100.0, score), reasons


def select_strike(chain, bias, max_extra_steps=2):
    """Returns dict {strike, type, token, symbol, ltp, oi, vol, score, reasons} or None."""
    if not chain or chain.get("status") != "OK":
        return None
    if bias not in ("BULLISH", "BEARISH"):
        return None

    atm = chain.get("atm")
    opt_type = "CE" if bias == "BULLISH" else "PE"
    side_data = chain.get("ce_data") if opt_type == "CE" else chain.get("pe_data")
    if not side_data:
        return None

    # Rank all strikes in the side
    scored = []
    for strike, entry in side_data.items():
        score, reasons = _score_option(
            {**entry, "strike": strike}, atm, bias
        )
        scored.append((score, strike, entry, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None

    best_score, best_strike, best_entry, best_reasons = scored[0]

    # Hard floor: must have some liquidity
    if best_entry.get("oi", 0) < 5000 or best_entry.get("vol", 0) < 1000:
        return None

    return {
        "strike": best_strike,
        "type": opt_type,
        "token": best_entry.get("token"),
        "symbol": best_entry.get("symbol"),
        "ltp": best_entry.get("ltp"),
        "oi": best_entry.get("oi"),
        "vol": best_entry.get("vol"),
        "score": round(best_score, 1),
        "reasons": best_reasons,
    }


def print_strike(s):
    if not s:
        print("  no strike selected")
        return
    print(f"  → {s['type']} {s['strike']:.0f}  score={s['score']}  "
          f"ltp=₹{s['ltp']:.2f}  oi={s['oi']}  vol={s['vol']}  "
          f"reasons={s['reasons']}")
