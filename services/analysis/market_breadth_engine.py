"""
Market Breadth Engine

Institutional market breadth analysis.
"""

from typing import Dict


def analyze_market_breadth(snapshot):

    """
    Expected snapshot:

    snapshot["market_breadth"] = {

        "advance": int,

        "decline": int,

        "unchanged": int,

        "new_highs": int,

        "new_lows": int,

    }
    """

    breadth = snapshot.get(
        "market_breadth",
        {},
    )

    advance = int(
        breadth.get(
            "advance",
            0,
        )
    )

    decline = int(
        breadth.get(
            "decline",
            0,
        )
    )

    unchanged = int(
        breadth.get(
            "unchanged",
            0,
        )
    )

    new_highs = int(
        breadth.get(
            "new_highs",
            0,
        )
    )

    new_lows = int(
        breadth.get(
            "new_lows",
            0,
        )
    )

    total = advance + decline + unchanged

    if total == 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "Market breadth unavailable",

            "metrics": {},

        }

    adr = advance / max(
        decline,
        1,
    )

    bull = 0
    bear = 0

    reasons = []

    # -------------------------------------
    # Advance / Decline Ratio
    # -------------------------------------

    if adr >= 2:

        bull += 4

        reasons.append(
            "Strong Advance Decline Ratio"
        )

    elif adr >= 1.2:

        bull += 2

        reasons.append(
            "Positive Advance Decline Ratio"
        )

    elif adr <= 0.5:

        bear += 4

        reasons.append(
            "Strong Decline Dominance"
        )

    elif adr <= 0.8:

        bear += 2

        reasons.append(
            "Negative Advance Decline Ratio"
        )

    # -------------------------------------
    # New Highs / New Lows
    # -------------------------------------

    if new_highs > new_lows:

        bull += 2

        reasons.append(
            "More New Highs"
        )

    elif new_lows > new_highs:

        bear += 2

        reasons.append(
            "More New Lows"
        )

    # -------------------------------------

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    confidence = min(

        100,

        round(

            45

            + abs(
                bull - bear
            ) * 8,

            2,

        ),

    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": ", ".join(reasons),

        "metrics": {

            "Advance": advance,

            "Decline": decline,

            "Unchanged": unchanged,

            "AdvanceDeclineRatio": round(
                adr,
                2,
            ),

            "NewHighs": new_highs,

            "NewLows": new_lows,

        },

    }