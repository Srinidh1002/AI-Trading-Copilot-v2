"""MCX decision engine — precision-first.
Replaces mcx_bias.py. Per MCX Precision-First spec §1, §4, §5, §6, §7, §9, §11, §12.

Design:
1. Compute four independent scores:
   TECHNICAL_DIRECTION_SCORE  (-100..+100)
   EXTERNAL_CONTEXT_SCORE     (-100..+100)
   OPTION_CHAIN_SCORE         (-100..+100)
   ENTRY_QUALITY_SCORE        (0..100)
2. Combine into LONG_CONFIDENCE and SHORT_CONFIDENCE (0..100)
3. Apply HARD GATES that override scores:
   - MTF BEARISH -> BUY_CALL BLOCKED
   - MTF BULLISH -> BUY_PUT BLOCKED
   - DISLOCATED/EVENT_DRIVEN regime -> all BLOCKED
   - RANGE regime without breakout -> trend entries BLOCKED
   - VWAP misalignment -> BLOCK
4. Return full decision dict with all evidence persisted.
Read-only. No trades.
"""

# ---- Weights (documented, versioned) ----
WEIGHTS = {
    "technical": 0.45,
    "external":  0.20,
    "chain":     0.20,
    "entry":     0.15,
}

# ---- Timeframe direction mapping ----
TF_WEIGHTS = {"1m": 0.5, "5m": 1.0, "15m": 1.5, "30m": 1.5, "1h": 2.0}


def _tf_dir(v):
    """-1 / 0 / +1"""
    if not v or v.get("status") != "OK":
        return 0
    t = v.get("trend", "FLAT")
    if t == "UP":   return 1
    if t == "DOWN": return -1
    return 0


def _technical_direction_score(mtf):
    """-100..+100 weighted consensus across timeframes."""
    if not mtf or mtf.get("status") != "OK":
        return 0, {}
    tfs = mtf.get("timeframes", {})
    num = 0.0
    den = 0.0
    detail = {}
    for tf, w in TF_WEIGHTS.items():
        v = tfs.get(tf, {})
        d = _tf_dir(v)
        detail[tf] = {"direction": v.get("trend", "UNKNOWN") if v.get("status") == "OK" else "UNKNOWN",
                      "score": d}
        num += w * d
        den += w
    if den == 0:
        return 0, detail
    return round((num / den) * 100, 2), detail


def _external_context_score(ctx):
    """-100..+100 from composite external regime."""
    if not ctx or ctx.get("status") != "OK":
        return 0, {}
    regime = ctx.get("composite_regime", "UNKNOWN")
    comp = ctx.get("composite_move_1d_pct") or 0.0
    mapping = {
        "STRONG_UP": 100, "UP": 70, "WEAK_UP": 35,
        "FLAT": 0,
        "STRONG_DOWN": -100, "DOWN": -70, "WEAK_DOWN": -35,
        "UNKNOWN": 0,
    }
    score = mapping.get(regime, 0)
    detail = {"regime": regime, "composite_pct": comp,
              "primary": {k: v.get("regime") for k, v in ctx.get("primary", {}).items()}}
    return score, detail


def _option_chain_score(chain, pcr_ema=1.0):
    """-100..+100 from chain PCR + max pain distance.
    Uses stable PCR (see mcx_chain.compute_stable_pcr).
    PCR contributes most; max pain only small adjustment.
    """
    if not chain or chain.get("status") != "OK":
        return 0, {}
    pcr = chain.get("pcr_oi")
    if pcr is None:
        return 0, {"pcr": None}

    # PCR → directional score (contrarian at extremes, neutral near 1)
    # 0.7 -> +30 bearish signal per old logic; test new convention:
    # For MCX crude (trending market), treat PCR as confirming not contrarian.
    # >1.2 = many puts written = often bullish continuation
    # <0.8 = many calls written = often bearish continuation
    if pcr >= 1.3:    pcr_score = 80
    elif pcr >= 1.15: pcr_score = 50
    elif pcr >= 1.05: pcr_score = 20
    elif pcr <= 0.7:  pcr_score = -80
    elif pcr <= 0.85: pcr_score = -50
    elif pcr <= 0.95: pcr_score = -20
    else:             pcr_score = 0

    # Max pain distance (small contribution)
    mp = chain.get("max_pain")
    fut = chain.get("future_ltp")
    mp_score = 0
    if mp and fut and mp > 0:
        dist_pct = (fut - mp) / mp * 100
        if dist_pct >= 1.0:   mp_score = 20    # above MP often -> writer pressure down
        elif dist_pct <= -1.0: mp_score = -20
        else: mp_score = int(dist_pct * 10)

    total = round(pcr_score * 0.8 + mp_score * 0.2, 2)
    detail = {
        "pcr": pcr,
        "pcr_score": pcr_score,
        "max_pain": mp,
        "mp_score": mp_score,
        "distance_pct": round(((fut - mp) / mp * 100), 2) if mp and fut else None,
    }
    return total, detail


def _entry_quality_for_side(mtf, chain, regime_dict, side, vwap_ctx=None):
    """Directional entry quality (0..100) for LONG or SHORT.
    Only counts evidence supporting that side.
    """
    if not mtf or mtf.get("status") != "OK":
        return 0, {}

    q = 0
    reasons = []
    tfs = mtf.get("timeframes", {})
    want = "UP" if side == "LONG" else "DOWN"
    opposite = "DOWN" if side == "LONG" else "UP"

    def _is(tf_name, direction):
        v = tfs.get(tf_name, {})
        if v.get("status") != "OK":
            return False
        return v.get("trend") == direction

    # 5m + 15m aligned for THIS side
    if _is("5m", want) and _is("15m", want):
        q += 30
        reasons.append(f"5m_15m_ALIGNED_{side}")
    elif _is("5m", opposite) and _is("15m", opposite):
        reasons.append(f"5m_15m_CONFLICT_{side}")

    # 1h confirms for THIS side
    if _is("1h", want):
        q += 20
        reasons.append(f"1h_CONFIRMS_{side}")

    # Regime supports THIS side
    reg = regime_dict.get("regime", "UNKNOWN")
    if side == "LONG" and reg in ("TREND_UP", "BREAKOUT_UP"):
        q += 25
        reasons.append(f"REGIME_{reg}")
    elif side == "SHORT" and reg in ("TREND_DOWN", "BREAKOUT_DOWN"):
        q += 25
        reasons.append(f"REGIME_{reg}")
    else:
        reasons.append(f"REGIME_{reg}")

    # ADX is side-agnostic (trend strength)
    adx = None
    for tf in ("15m", "5m"):
        v = tfs.get(tf, {})
        if v.get("status") == "OK" and v.get("adx") is not None:
            adx = v["adx"]
            break
    if adx is not None:
        if adx >= 25:
            q += 15
            reasons.append(f"ADX_{adx:.0f}_STRONG")
        elif adx >= 18:
            q += 8
            reasons.append(f"ADX_{adx:.0f}_MODERATE")
        else:
            reasons.append(f"ADX_{adx:.0f}_WEAK")

    # Chain liquidity is side-agnostic
    if chain and chain.get("status") == "OK":
        ce_data = chain.get("ce_data", {})
        pe_data = chain.get("pe_data", {})
        total_oi = sum(v.get("oi", 0) for v in ce_data.values()) + \
                   sum(v.get("oi", 0) for v in pe_data.values())
        if total_oi >= 1_000_000:
            q += 10
            reasons.append("CHAIN_DEEP_LIQ")
        elif total_oi >= 200_000:
            q += 5
            reasons.append("CHAIN_OK_LIQ")
        else:
            reasons.append("CHAIN_THIN")

    return min(100, q), {"reasons": reasons, "adx_used": adx}


def _entry_quality_scores(mtf, chain, regime_dict, vwap_ctx=None):
    """Return (long_q, short_q, detail_dict)."""
    long_q, long_d = _entry_quality_for_side(mtf, chain, regime_dict, "LONG", vwap_ctx)
    short_q, short_d = _entry_quality_for_side(mtf, chain, regime_dict, "SHORT", vwap_ctx)
    return long_q, short_q, {"long": long_d, "short": short_d}


def _combine_scores(tech, ext, chain_s, long_q, short_q):
    """Combine into LONG_CONFIDENCE and SHORT_CONFIDENCE (0..100).
    LONG uses long_q; SHORT uses short_q. Directional entry quality.
    """
    tech_mag = abs(tech) / 100.0
    ext_mag = abs(ext) / 100.0
    chain_mag = abs(chain_s) / 100.0

    ext_agrees_long = (ext > 0)
    ext_agrees_short = (ext < 0)
    chain_agrees_long = (chain_s > 0)
    chain_agrees_short = (chain_s < 0)

    long_entry_factor = (long_q / 100.0)
    short_entry_factor = (short_q / 100.0)

    long_base = 0.0
    if tech > 0:
        long_base += tech_mag * WEIGHTS["technical"]
    if ext_agrees_long:
        long_base += ext_mag * WEIGHTS["external"]
    if chain_agrees_long:
        long_base += chain_mag * WEIGHTS["chain"]
    long_base += long_entry_factor * WEIGHTS["entry"]
    LONG_CONFIDENCE = max(0, min(100, int(round(long_base * 100))))

    short_base = 0.0
    if tech < 0:
        short_base += tech_mag * WEIGHTS["technical"]
    if ext_agrees_short:
        short_base += ext_mag * WEIGHTS["external"]
    if chain_agrees_short:
        short_base += chain_mag * WEIGHTS["chain"]
    short_base += short_entry_factor * WEIGHTS["entry"]
    SHORT_CONFIDENCE = max(0, min(100, int(round(short_base * 100))))

    return LONG_CONFIDENCE, SHORT_CONFIDENCE


def _apply_hard_gates(tech, LONG_CONF, SHORT_CONF, mtf, regime_dict, ctx, vwap_ctx):
    """Return list of hard blocker codes. Non-empty = NO_TRADE regardless of confidence."""
    blockers = []

    tfs = (mtf or {}).get("timeframes", {})
    d5 = _tf_dir(tfs.get("5m", {}))
    d15 = _tf_dir(tfs.get("15m", {}))
    d1h = _tf_dir(tfs.get("1h", {}))

    reg = regime_dict.get("regime", "UNKNOWN")

    # §1 hard gates
    if LONG_CONF >= 60:
        if d15 == -1:
            blockers.append("MTF_15M_BEARISH_BLOCKS_CALL")
        if d1h == -1:
            blockers.append("MTF_1H_BEARISH_BLOCKS_CALL")

    if SHORT_CONF >= 60:
        if d15 == 1:
            blockers.append("MTF_15M_BULLISH_BLOCKS_PUT")
        if d1h == 1:
            blockers.append("MTF_1H_BULLISH_BLOCKS_PUT")

    # Regime blocks
    if reg in ("DISLOCATED", "EVENT_DRIVEN"):
        blockers.append(f"REGIME_{reg}_BLOCKED")

    if reg == "HIGH_VOLATILITY":
        blockers.append("REGIME_HIGH_VOL_BLOCKED")

    # RANGE regime without breakout -> no trend entries
    if reg == "RANGE":
        blockers.append("REGIME_RANGE_NO_TREND")

    # VWAP alignment for trend entries
    if vwap_ctx and vwap_ctx.get("vwap") is not None:
        pos = vwap_ctx.get("position")
        if LONG_CONF >= 60 and pos == "BELOW":
            blockers.append("VWAP_BELOW_BLOCKS_LONG")
        if SHORT_CONF >= 60 and pos == "ABOVE":
            blockers.append("VWAP_ABOVE_BLOCKS_SHORT")

    # Data quality
    if not mtf or mtf.get("status") != "OK":
        blockers.append("MTF_UNAVAILABLE")

    return blockers


def compose(chain, ctx, mtf, regime_dict, vwap_ctx=None, event_state=None,
            stable_pcr=None, minutes_in_trade=None):
    """Main entry point. Returns full decision dict.
    Extended with optional event_state + stable_pcr per spec §2, §22.
    """
    tech, tech_detail = _technical_direction_score(mtf)
    ext, ext_detail = _external_context_score(ctx)

    # StablePCR is authoritative when explicitly supplied.
    #
    # V4 certification rule:
    # - stable_pcr is None:
    #     preserve legacy/non-StablePCR compose behaviour.
    # - stable_pcr status == OK:
    #     use StablePCR evidence.
    # - stable_pcr supplied but status != OK:
    #     do NOT silently fall back to raw chain PCR.
    #     The chain PCR score is neutralized and a hard blocker is
    #     added below, forcing NO_TRADE.
    chain_for_score = dict(chain) if chain else {}
    stable_pcr_status = None

    if stable_pcr is not None:
        stable_pcr_status = (
            stable_pcr.get("status")
            if isinstance(stable_pcr, dict)
            else None
        )

        if stable_pcr_status == "OK":
            chain_for_score["pcr_oi"] = (
                stable_pcr.get("PCR_EMA_3")
                or stable_pcr.get("PCR_TOTAL_OI")
            )
            chain_for_score["pcr_stable_source"] = True
            chain_for_score["pcr_raw"] = stable_pcr.get("PCR_TOTAL_OI")
            chain_for_score["pcr_change_rate"] = stable_pcr.get(
                "PCR_CHANGE_RATE"
            )
        else:
            chain_for_score["pcr_oi"] = None
            chain_for_score["pcr_stable_source"] = False

    chain_s, chain_detail = _option_chain_score(chain_for_score)
    long_q, short_q, entry_detail = _entry_quality_scores(mtf, chain, regime_dict, vwap_ctx)

    LONG_CONF, SHORT_CONF = _combine_scores(tech, ext, chain_s, long_q, short_q)

    blockers = _apply_hard_gates(tech, LONG_CONF, SHORT_CONF, mtf, regime_dict, ctx, vwap_ctx)

    # V4 fail-closed StablePCR authority.
    #
    # Only applies when StablePCR was explicitly supplied by the
    # canonical MCX runtime. Legacy callers that omit stable_pcr keep
    # their historical behaviour.
    if stable_pcr is not None and stable_pcr_status != "OK":
        blockers.append(
            f"STABLE_PCR_{stable_pcr_status or 'UNAVAILABLE'}"
        )

    # Event risk gate (spec §22)
    if event_state and event_state.get("block_entries"):
        blockers.append(f"EVENT_RISK_{event_state.get('event')}_BLOCKS")

    # Determine action
    ENTRY_THRESHOLD = 70  # documented start value; calibrate later

    if blockers:
        action = "NO_TRADE"
        bias = "NEUTRAL"
    elif LONG_CONF >= ENTRY_THRESHOLD and LONG_CONF > SHORT_CONF + 15:
        action = "BUY_CALL"
        bias = "BULLISH"
    elif SHORT_CONF >= ENTRY_THRESHOLD and SHORT_CONF > LONG_CONF + 15:
        action = "BUY_PUT"
        bias = "BEARISH"
    else:
        action = "WAIT"
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "action": action,
        "LONG_CONFIDENCE": LONG_CONF,
        "SHORT_CONFIDENCE": SHORT_CONF,
        "TECHNICAL_DIRECTION_SCORE": tech,
        "EXTERNAL_CONTEXT_SCORE": ext,
        "OPTION_CHAIN_SCORE": chain_s,
        "LONG_ENTRY_QUALITY": long_q,
        "SHORT_ENTRY_QUALITY": short_q,
        "ENTRY_QUALITY_SCORE": max(long_q, short_q),
        "HARD_BLOCKERS": blockers,
        "regime": regime_dict.get("regime"),
        "regime_confidence": regime_dict.get("confidence"),
        "detail": {
            "technical": tech_detail,
            "external": ext_detail,
            "chain": chain_detail,
            "entry": entry_detail,
        },
    }


def print_decision(d):
    print(f"\nMCX DECISION:")
    print(f"  LONG_CONFIDENCE  = {d['LONG_CONFIDENCE']}")
    print(f"  SHORT_CONFIDENCE = {d['SHORT_CONFIDENCE']}")
    print(f"  TECHNICAL_SCORE  = {d['TECHNICAL_DIRECTION_SCORE']}")
    print(f"    per-TF:")
    for tf, v in d.get("detail", {}).get("technical", {}).items():
        print(f"      {tf:>3}  {v.get('direction')}")
    print(f"  EXTERNAL_SCORE   = {d['EXTERNAL_CONTEXT_SCORE']}")
    ext_d = d.get("detail", {}).get("external", {})
    print(f"    regime={ext_d.get('regime')}  composite={ext_d.get('composite_pct')}%")
    for k, v in (ext_d.get("primary") or {}).items():
        print(f"      {k:<8} -> {v}")
    print(f"  CHAIN_SCORE      = {d['OPTION_CHAIN_SCORE']}")
    ch_d = d.get("detail", {}).get("chain", {})
    if ch_d:
        print(f"    pcr={ch_d.get('pcr')}  pcr_score={ch_d.get('pcr_score')}  "
              f"max_pain={ch_d.get('max_pain')}  mp_score={ch_d.get('mp_score')}  "
              f"dist_pct={ch_d.get('distance_pct')}")
    print(f"  LONG_ENTRY_QUALITY  = {d.get('LONG_ENTRY_QUALITY')}")
    print(f"    reasons={d.get('detail', {}).get('entry', {}).get('long', {}).get('reasons', [])}")
    print(f"  SHORT_ENTRY_QUALITY = {d.get('SHORT_ENTRY_QUALITY')}")
    print(f"    reasons={d.get('detail', {}).get('entry', {}).get('short', {}).get('reasons', [])}")
    print(f"  REGIME           = {d['regime']} (conf={d['regime_confidence']})")
    print(f"  ACTION           = {d['action']} ({d['bias']})")
    if d["HARD_BLOCKERS"]:
        print(f"  HARD_BLOCKERS    = {d['HARD_BLOCKERS']}")
    else:
        print(f"  HARD_BLOCKERS    = (none)")


if __name__ == "__main__":
    print("MCX decision module loaded OK")
