"""
Phase 3 Strategy Engine
"""


def strategy_engine(
    technical,
    market,
    option,
    sentiment,
):

    bull = (
        technical.get("bull_score", 0)
        + market.get("bull_score", 0)
        + option.get("bull", option.get("bull_score", 0))
        + sentiment.get("bull", sentiment.get("bull_score", 0))
    )

    bear = (
        technical.get("bear_score", 0)
        + market.get("bear_score", 0)
        + option.get("bear", option.get("bear_score", 0))
        + sentiment.get("bear", sentiment.get("bear_score", 0))
    )

    confidence = abs(bull - bear)

    if bull >= bear + 20:
        signal = "BUY"

    elif bear >= bull + 20:
        signal = "SELL"

    else:
        signal = "HOLD"

    return {

        "signal": signal,

        "bull": bull,

        "bear": bear,

        "confidence": confidence,

    }