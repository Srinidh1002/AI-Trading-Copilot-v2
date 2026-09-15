"""MCX setup classifier — spec §13.
Only three setups certified for CRUDEOILM: TREND_CONTINUATION, BREAKOUT_RETEST, TREND_PULLBACK.
All other patterns yield NO_SETUP.
"""

APPROVED_SETUPS = ("TREND_CONTINUATION", "BREAKOUT_RETEST", "TREND_PULLBACK")


def _trend_aligned(mtf, direction):
    """Check 5m + 15m + 30m agree on direction."""
    tfs = (mtf or {}).get("timeframes", {})
    want = "UP" if direction == "BULLISH" else "DOWN"
    cnt = 0
    for tf in ("5m", "15m", "30m"):
        v = tfs.get(tf, {})
        if v.get("status") == "OK" and v.get("trend") == want:
            cnt += 1
    return cnt >= 2


def _vwap_confirms(structure, direction):
    pos = (structure or {}).get("vwap_position")
    if direction == "BULLISH":
        return pos in ("ABOVE", "AT")
    if direction == "BEARISH":
        return pos in ("BELOW", "AT")
    return False


def classify(decision, regime, structure, mtf, price_oi_state=None):
    """Returns dict: {setup, blocked, reasons}."""
    action = decision.get("action")
    regime_name = (regime or {}).get("regime", "UNKNOWN")

    if action not in ("BUY_CALL", "BUY_PUT"):
        return {"setup": "NONE", "blocked": True, "reasons": ["NO_DIRECTIONAL_ACTION"]}

    direction = "BULLISH" if action == "BUY_CALL" else "BEARISH"

    # Setup 1: TREND_CONTINUATION
    if regime_name in ("TREND_UP", "TREND_DOWN"):
        aligned = _trend_aligned(mtf, direction)
        vwap_ok = _vwap_confirms(structure, direction)
        struct_dir = (structure or {}).get("overall_structure", "MIXED")
        struct_ok = (direction == "BULLISH" and "BULLISH" in struct_dir) or \
                    (direction == "BEARISH" and "BEARISH" in struct_dir)
        if aligned and vwap_ok and struct_ok:
            return {
                "setup": "TREND_CONTINUATION",
                "blocked": False,
                "reasons": ["MTF_ALIGNED", "VWAP_OK", "STRUCTURE_OK"],
            }

    # Setup 2: BREAKOUT_RETEST
    if regime_name in ("BREAKOUT_UP", "BREAKOUT_DOWN"):
        want_regime = "BREAKOUT_UP" if direction == "BULLISH" else "BREAKOUT_DOWN"
        if regime_name == want_regime:
            aligned = _trend_aligned(mtf, direction)
            if aligned:
                return {
                    "setup": "BREAKOUT_RETEST",
                    "blocked": False,
                    "reasons": ["BREAKOUT_REGIME", "MTF_ALIGNED"],
                }

    # Setup 3: TREND_PULLBACK — trend regime but 5m pulled back to VWAP
    if regime_name in ("TREND_UP", "TREND_DOWN"):
        vwap_pos = (structure or {}).get("vwap_position")
        dist = abs((structure or {}).get("vwap_distance_pct", 99))
        near_vwap = dist <= 0.15
        aligned_15 = _trend_aligned(mtf, direction)
        if near_vwap and aligned_15:
            return {
                "setup": "TREND_PULLBACK",
                "blocked": False,
                "reasons": ["NEAR_VWAP", "MTF_ALIGNED"],
            }

    return {"setup": "NO_SETUP", "blocked": True,
            "reasons": [f"REGIME_{regime_name}_NO_MATCH"]}


def describe(s):
    if s.get("blocked"):
        return f"NO_SETUP ({','.join(s.get('reasons', []))})"
    return f"{s['setup']} ({','.join(s.get('reasons', []))})"


if __name__ == "__main__":
    print("mcx_setup module loaded OK")
    print(f"Approved setups: {APPROVED_SETUPS}")
