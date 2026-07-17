"""
Confidence Engine V1
"""

def calculate_confidence(snapshot):

    score = 0
    reasons = []

    indicators = snapshot["indicators"]

    # EMA
    if (
        indicators["EMA20"] >
        indicators["EMA50"] >
        indicators["EMA200"]
    ):
        score += 25
        reasons.append("EMA Bullish")

    # RSI
    if 55 <= indicators["RSI"] <= 70:
        score += 15
        reasons.append("RSI Healthy")

    # MACD
    if indicators["MACD_TREND"] == "Bullish":
        score += 20
        reasons.append("MACD Bullish")

    # ADX
    if indicators["ADX"] >= 25:
        score += 15
        reasons.append("Strong Trend")

    return {
        "confidence": score,
        "reasons": reasons
    }