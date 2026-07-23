"""
FII / DII Institutional Money Flow Engine

Analyzes daily institutional cash market activity.
"""

from datetime import date


def analyze_fii_dii(snapshot):

    """
    Expected snapshot format:

    snapshot["institutional_flow"] = {

        "FII": float,
        "DII": float,

    }

    Values should be in Crores.
    """

    flow = snapshot.get(
        "institutional_flow",
        {},
    )

    fii = float(
        flow.get(
            "FII",
            0,
        )
    )

    dii = float(
        flow.get(
            "DII",
            0,
        )
    )

    net = fii + dii

    bull = 0
    bear = 0

    reasons = []

    # -----------------------------------------
    # FII Analysis
    # -----------------------------------------

    if fii >= 3000:

        bull += 4
        reasons.append("Strong FII Buying")

    elif fii >= 1000:

        bull += 2
        reasons.append("Moderate FII Buying")

    elif fii <= -3000:

        bear += 4
        reasons.append("Strong FII Selling")

    elif fii <= -1000:

        bear += 2
        reasons.append("Moderate FII Selling")

    # -----------------------------------------
    # DII Analysis
    # -----------------------------------------

    if dii >= 2000:

        bull += 2
        reasons.append("Strong DII Buying")

    elif dii <= -2000:

        bear += 2
        reasons.append("Strong DII Selling")

    # -----------------------------------------
    # Net Institutional Flow
    # -----------------------------------------

    if net >= 3000:

        bull += 3
        reasons.append("Strong Net Institutional Buying")

    elif net >= 1000:

        bull += 2
        reasons.append("Net Institutional Buying")

    elif net <= -3000:

        bear += 3
        reasons.append("Strong Net Institutional Selling")

    elif net <= -1000:

        bear += 2
        reasons.append("Net Institutional Selling")

    # -----------------------------------------

    if bull >= bear + 2:

        signal = "BULLISH"

    elif bear >= bull + 2:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    dominance = abs(
        bull - bear
    )

    confidence = min(
        100,
        round(
            45 + dominance * 8,
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

            "FII": fii,

            "DII": dii,

            "NetFlow": net,

            "Date": str(date.today()),

        },

    }