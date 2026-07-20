"""
Reasoning Engine V1
"""


def generate_reasoning(decision):

    reasons = []

    trend = decision["trend"]

    if trend["trend"] == "Bullish":
        reasons.append("Overall market trend is Bullish.")

    elif trend["trend"] == "Bearish":
        reasons.append("Overall market trend is Bearish.")

    if trend["momentum"] == "Bullish":
        reasons.append("Momentum supports upward movement.")

    elif trend["momentum"] == "Bearish":
        reasons.append("Momentum supports downward movement.")

    reasons.append(
        f"Trend strength is {trend['strength']}."
    )

    reasons.append(
        f"Confidence Score : {decision['confidence']}%"
    )

    return reasons