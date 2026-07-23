"""
Market Strength Engine

Combines multiple institutional engines to estimate
overall market strength.
"""


def analyze_market_strength(snapshot):

    trend = snapshot.get("trend_analysis", {})
    volume = snapshot.get("volume_analysis", {})
    breadth = snapshot.get("market_breadth_analysis", {})
    fii = snapshot.get("fii_dii_analysis", {})
    vix = snapshot.get("vix_analysis", {})
    regime = snapshot.get("market_regime_analysis", {})
    liquidity = snapshot.get("liquidity_analysis", {})
    correlation = snapshot.get("correlation_analysis", {})

    engines = [

        trend,
        volume,
        breadth,
        fii,
        vix,
        regime,
        liquidity,
        correlation,

    ]

    bull = 0
    bear = 0

    confidence_sum = 0

    reasons = []

    active = 0

    for engine in engines:

        if not engine:
            continue

        active += 1

        bull += engine.get(
            "bull_score",
            0,
        )

        bear += engine.get(
            "bear_score",
            0,
        )

        confidence_sum += engine.get(
            "confidence",
            0,
        )

        reason = engine.get(
            "reason",
            "",
        )

        if reason:
            reasons.append(reason)

    if active == 0:

        return {

            "signal": "UNKNOWN",

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "strength": 0,

            "reason": "No market strength data",

            "metrics": {},

        }

    if bull >= bear + 5:

        signal = "VERY_BULLISH"

    elif bull > bear:

        signal = "BULLISH"

    elif bear >= bull + 5:

        signal = "VERY_BEARISH"

    elif bear > bull:

        signal = "BEARISH"

    else:

        signal = "NEUTRAL"

    strength = round(

        abs(
            bull - bear
        )

        / max(
            bull + bear,
            1,
        )

        * 100,

        2,

    )

    confidence = round(

        confidence_sum / active,

        2,

    )

    return {

        "signal": signal,

        "bull_score": bull,

        "bear_score": bear,

        "strength": strength,

        "confidence": confidence,

        "reason": " | ".join(reasons),

        "metrics": {

            "BullScore": bull,

            "BearScore": bear,

            "Strength": strength,

            "Engines": active,

        },

    }