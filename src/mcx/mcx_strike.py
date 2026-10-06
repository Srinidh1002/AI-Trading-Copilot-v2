"""MCX strike selection — pick best CE/PE given bias + chain. READ-ONLY."""

MIN_OPTION_OI = 5_000
MIN_OPTION_VOLUME = 1_000
DIAGNOSTIC_TOP_N = 5


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
    if oi >= 200000:
        score += 25
        reasons.append("DEEP_OI")
    elif oi >= 100000:
        score += 15
        reasons.append("HIGH_OI")
    elif oi >= 50000:
        score += 8
        reasons.append("MED_OI")
    elif oi < 10000:
        reasons.append("THIN_OI")

    # Volume
    if vol >= 150000:
        score += 20
        reasons.append("HIGH_VOL")
    elif vol >= 50000:
        score += 12
        reasons.append("MED_VOL")
    elif vol >= 10000:
        score += 6
        reasons.append("LOW_VOL")
    else:
        reasons.append("THIN_VOL")

    # Distance from ATM: prefer near-ATM
    if atm_strike:
        dist = abs(strike - atm_strike)
        if dist <= 50:
            score += 15
            reasons.append("ATM")
        elif dist <= 100:
            score += 10
            reasons.append("NEAR_ATM")
        elif dist <= 200:
            score += 4
            reasons.append("OTM")
        else:
            reasons.append("FAR_OTM")

    return min(100.0, score), reasons


def _candidate_record(score, strike, entry, reasons):
    oi = float(entry.get("oi", 0) or 0)
    vol = float(entry.get("vol", 0) or 0)
    ltp = float(entry.get("ltp", 0) or 0)
    passes_oi = oi >= MIN_OPTION_OI
    passes_volume = vol >= MIN_OPTION_VOLUME
    return {
        "strike": strike,
        "ltp": ltp,
        "oi": oi,
        "vol": vol,
        "score": round(score, 1),
        "reasons": list(reasons),
        "passes_oi": passes_oi,
        "passes_volume": passes_volume,
        "eligible": bool(ltp > 0 and passes_oi and passes_volume),
        "token": entry.get("token"),
        "symbol": entry.get("symbol"),
    }


def select_strike_with_diagnostics(chain, bias, max_extra_steps=2):
    """Return ``(selection, diagnostics)`` without provider calls.

    R18 fixes an ordering defect in the prior selector: the old code ranked all
    candidates first, inspected only the top-ranked row, and returned ``None``
    when that one row missed the liquidity floor.  A lower-ranked but actually
    eligible option was therefore ignored.  R18 filters by the existing hard
    liquidity floors first and then selects the best eligible candidate.

    ``max_extra_steps`` remains for API compatibility; strike availability is
    already bounded by the chain builder.
    """
    del max_extra_steps

    diag = {
        "status": "UNKNOWN",
        "bias": bias,
        "option_type": None,
        "atm": None,
        "min_oi": MIN_OPTION_OI,
        "min_volume": MIN_OPTION_VOLUME,
        "candidate_count": 0,
        "eligible_count": 0,
        "top_candidates": [],
    }

    if not chain or chain.get("status") != "OK":
        diag["status"] = "CHAIN_UNAVAILABLE"
        return None, diag

    if bias not in ("BULLISH", "BEARISH"):
        diag["status"] = "INVALID_BIAS"
        return None, diag

    atm = chain.get("atm")
    opt_type = "CE" if bias == "BULLISH" else "PE"
    side_data = chain.get("ce_data") if opt_type == "CE" else chain.get("pe_data")
    diag["option_type"] = opt_type
    diag["atm"] = atm

    if not side_data:
        diag["status"] = "NO_SIDE_DATA"
        return None, diag

    scored = []
    for strike, entry in side_data.items():
        score, reasons = _score_option({**entry, "strike": strike}, atm, bias)
        candidate = _candidate_record(score, strike, entry, reasons)
        scored.append((score, strike, entry, reasons, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    diag["candidate_count"] = len(scored)
    diag["top_candidates"] = [row[4] for row in scored[:DIAGNOSTIC_TOP_N]]

    eligible = [row for row in scored if row[4]["eligible"]]
    diag["eligible_count"] = len(eligible)

    if not eligible:
        diag["status"] = "NO_ELIGIBLE_LIQUIDITY"
        return None, diag

    best_score, best_strike, best_entry, best_reasons, _ = eligible[0]
    diag["status"] = "SELECTED"
    diag["selected_strike"] = best_strike
    diag["selected_score"] = round(best_score, 1)

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
    }, diag


def select_strike(chain, bias, max_extra_steps=2):
    """Return the best liquidity-eligible option or ``None``.

    A failed directional selection emits bounded evidence for the top five
    candidates.  This is intentionally local logging only: it does not make
    any provider call and does not lower the existing liquidity floors.
    """
    selection, diag = select_strike_with_diagnostics(
        chain,
        bias,
        max_extra_steps=max_extra_steps,
    )
    if selection is None and diag.get("status") == "NO_ELIGIBLE_LIQUIDITY":
        for line in format_strike_diagnostics(diag):
            print(f"  {line}")
    return selection


def format_strike_diagnostics(diag):
    """Compact stable diagnostic line(s) for operator logs."""
    if not isinstance(diag, dict):
        return ["STRIKE_DIAG status=INVALID_DIAGNOSTIC"]

    lines = [
        "STRIKE_DIAG "
        f"status={diag.get('status')} side={diag.get('option_type')} "
        f"atm={diag.get('atm')} candidates={diag.get('candidate_count')} "
        f"eligible={diag.get('eligible_count')} "
        f"floor_oi={diag.get('min_oi')} floor_vol={diag.get('min_volume')}"
    ]

    for rank, row in enumerate(diag.get("top_candidates") or [], start=1):
        lines.append(
            "STRIKE_CANDIDATE "
            f"rank={rank} strike={row.get('strike')} ltp={row.get('ltp')} "
            f"oi={row.get('oi')} vol={row.get('vol')} score={row.get('score')} "
            f"eligible={row.get('eligible')} "
            f"passes_oi={row.get('passes_oi')} "
            f"passes_vol={row.get('passes_volume')}"
        )

    return lines


def print_strike(s):
    if not s:
        print("  no strike selected")
        return
    print(
        f"  → {s['type']} {s['strike']:.0f}  score={s['score']}  "
        f"ltp=₹{s['ltp']:.2f}  oi={s['oi']}  vol={s['vol']}  "
        f"reasons={s['reasons']}"
    )
