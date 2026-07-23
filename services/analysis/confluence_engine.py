"""
Confluence Engine

Combines every analysis engine into a single
institutional confluence score.
"""


def analyze_confluence(snapshot):

    analyses = [

        snapshot.get("trend_analysis", {}),
        snapshot.get("structure_analysis", {}),
        snapshot.get("candlestick_analysis", {}),
        snapshot.get("volume_analysis", {}),
        snapshot.get("market_breadth_analysis", {}),
        snapshot.get("market_regime_analysis", {}),
        snapshot.get("liquidity_analysis", {}),
        snapshot.get("correlation_analysis", {}),
        snapshot.get("fii_dii_analysis", {}),
        snapshot.get("vix_analysis", {}),
        snapshot.get("news_analysis", {}),
        snapshot.get("economic_analysis", {}),
        snapshot.get("execution_quality_analysis", {}),
        snapshot.get("portfolio_risk_analysis", {}),
        snapshot.get("market_strength_analysis", {}),

    ]

    bull = 0
    bear = 0

    confidence_sum = 0

    active = 0

    reasons = []

    for analysis in analyses:

        if not analysis:
            continue

        active += 1

        bull += analysis.get(
            "bull_score",
            0,
        )

        bear += analysis.get(
            "bear_score",
            0,
        )

        confidence_sum += analysis.get(
            "confidence",
            0,
        )

        reason = analysis.get(
            "reason",
            "",
        )

        if reason:

            reasons.append(reason)

    if active == 0:

        return {

            "signal": "UNKNOWN",

            "confluence_score": 0,

            "bull_score": 0,

            "bear_score": 0,

            "confidence": 0,

            "reason": "No confluence available",

            "metrics": {},

        }

    total = bull + bear

    if total == 0:

        confluence = 50

    else:

        confluence = round(

            (bull / total) * 100,

            2,

        )

    if confluence >= 75:

        signal = "STRONG_BUY"

    elif confluence >= 60:

        signal = "BUY"

    elif confluence <= 25:

        signal = "STRONG_SELL"

    elif confluence <= 40:

        signal = "SELL"

    else:

        signal = "NEUTRAL"

    confidence = round(

        confidence_sum / active,

        2,

    )

    return {

        "signal": signal,

        "confluence_score": confluence,

        "bull_score": bull,

        "bear_score": bear,

        "confidence": confidence,

        "reason": " | ".join(reasons),

        "metrics": {

            "ActiveEngines": active,

            "BullScore": bull,

            "BearScore": bear,

            "ConfluenceScore": confluence,

        },

    }