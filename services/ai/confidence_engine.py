"""
Confidence Engine

Calculates confidence score for the final trade.
"""


def calculate_confidence(
    trend,
    structure,
    candle,
    smart_money,
):
    """
    Calculate confidence score.

    Returns
    -------
    dict
    """

    score = 0
    reasons = []

    score += trend.get("confidence", 0) * 0.40
    score += structure.get("confidence", 0) * 0.20
    score += candle.get("confidence", 0) * 0.10
    score += smart_money.get("confidence", 0) * 0.30

    if trend["signal"] != "SIDEWAYS":
        reasons.append("Trend confirmed")

    if structure["signal"] != "RANGE":
        reasons.append("Market structure confirmed")

    if candle["signal"] != "NONE":
        reasons.append("Candlestick confirmation")

    if smart_money["signal"] == "STRONG":
        reasons.append("Smart Money confirmation")

    confidence = round(min(score, 100), 2)

    if confidence >= 80:
        grade = "A"

    elif confidence >= 65:
        grade = "B"

    elif confidence >= 50:
        grade = "C"

    else:
        grade = "D"

    return {
        "confidence": confidence,
        "grade": grade,
        "reason": ", ".join(reasons),
    }