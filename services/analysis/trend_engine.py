"""
Trend Engine

Determines the overall market trend using multiple indicators.
"""


def analyze_trend(snapshot):
    """
    Analyze market trend from indicator outputs.

    Returns
    -------
    dict
    """

    indicators = snapshot["indicators"]

    ema = indicators["ema"]
    macd = indicators["macd"]
    adx = indicators["adx"]
    vwap = indicators["vwap"]

    bull_score = 0
    bear_score = 0
    reasons = []

    if ema["trend"] == "BULLISH":
        bull_score += 2
        reasons.append("EMA Bullish")
    elif ema["trend"] == "BEARISH":
        bear_score += 2
        reasons.append("EMA Bearish")

    if macd["trend"] == "BULLISH":
        bull_score += 2
        reasons.append("MACD Bullish")
    elif macd["trend"] == "BEARISH":
        bear_score += 2
        reasons.append("MACD Bearish")

    if vwap["trend"] == "ABOVE_VWAP":
        bull_score += 1
        reasons.append("Above VWAP")
    elif vwap["trend"] == "BELOW_VWAP":
        bear_score += 1
        reasons.append("Below VWAP")

    confidence = min(100, adx["adx"] * 2)

    if bull_score > bear_score:
        signal = "BULLISH"
    elif bear_score > bull_score:
        signal = "BEARISH"
    else:
        signal = "SIDEWAYS"

    return {
        "signal": signal,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "confidence": round(confidence, 2),
        "reason": ", ".join(reasons),
    }