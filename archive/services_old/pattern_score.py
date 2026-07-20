"""
Pattern Score Engine V1
"""


def pattern_score(pattern_result):

    signal = pattern_result["signal"]

    if signal == "Bullish":
        return {
            "score": 15,
            "bias": "Bullish"
        }

    if signal == "Bearish":
        return {
            "score": 15,
            "bias": "Bearish"
        }

    return {
        "score": 5,
        "bias": "Neutral"
    }