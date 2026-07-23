"""
Phase 3 Strategy Engine
"""
from models.engine_contract import EngineResult

def strategy_engine(
    technical,
    market,
    option,
    sentiment,
):

    bull = (
        technical.get("bull_score", 0)
        + market.get("bull_score", 0)
        + option.get("bull_score", option.get("bull", 0))
        + sentiment.get("bull_score", sentiment.get("bull", 0))
    )

    bear = (
        technical.get("bear_score", 0)
        + market.get("bear_score", 0)
        + option.get("bear_score", option.get("bear", 0))
        + sentiment.get("bear_score", sentiment.get("bear", 0))
    )

    confidence = abs(bull - bear)

    if bull >= bear + 20:
        signal = "BUY"
        trend = "BULLISH"

    elif bear >= bull + 20:
        signal = "SELL"
        trend = "BEARISH"

    else:
        signal = "HOLD"
        trend = "NEUTRAL"

    reasons = []

    if signal == "BUY":
        reasons.append("Bullish score is significantly higher than bearish score.")

    elif signal == "SELL":
        reasons.append("Bearish score is significantly higher than bullish score.")

    else:
        reasons.append("Bullish and bearish scores are too close to justify a trade.")

    metadata = {}

    return EngineResult(
        signal=signal,
        trend=trend,
        bull_score=bull,
        bear_score=bear,
        confidence=confidence,
        reasons=reasons,
        metadata={},
    ).to_dict()