"""
India VIX Engine

Analyzes market volatility and its impact on trading decisions.
"""

import math


LOW_VIX = 13
NORMAL_VIX = 18
HIGH_VIX = 25


def analyze_vix(snapshot):

    """
    Expected snapshot:

    snapshot["vix"] = 14.82
    """

    vix = float(snapshot.get("vix", 0))

    bull = 0
    bear = 0

    reasons = []

    if vix <= 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "India VIX unavailable",

            "metrics": {},

        }

    # ----------------------------------------
    # Low Volatility
    # ----------------------------------------

    if vix <= LOW_VIX:

        regime = "Low"

        bull += 2

        reasons.append(
            "Low volatility environment"
        )

    # ----------------------------------------
    # Normal Volatility
    # ----------------------------------------

    elif vix <= NORMAL_VIX:

        regime = "Normal"

        bull += 1

        reasons.append(
            "Healthy market volatility"
        )

    # ----------------------------------------
    # Elevated Volatility
    # ----------------------------------------

    elif vix <= HIGH_VIX:

        regime = "High"

        bear += 2

        reasons.append(
            "High volatility detected"
        )

    # ----------------------------------------
    # Extreme Volatility
    # ----------------------------------------

    else:

        regime = "Extreme"

        bear += 4

        reasons.append(
            "Extreme fear in market"
        )

    # ----------------------------------------
    # Signal
    # ----------------------------------------

    if bull >= bear + 2:

        signal = "LOW_VOLATILITY"

    elif bear >= bull + 2:

        signal = "HIGH_VOLATILITY"

    else:

        signal = "NEUTRAL"

    confidence = min(
        100,
        round(
            55 + abs(bull - bear) * 10,
            2,
        ),
    )

    # ----------------------------------------
    # Expected Daily Move
    # ----------------------------------------

    expected_move_percent = vix / math.sqrt(252)

    metrics = {

        "VIX": round(vix, 2),

        "Regime": regime,

        "ExpectedMovePercent": round(
            expected_move_percent,
            2,
        ),

    }

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": ", ".join(reasons),

        "metrics": metrics,

    }