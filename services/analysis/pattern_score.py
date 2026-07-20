"""Backward-compatible pattern-score helper."""


def pattern_score(pattern_result):
    """Return the legacy score representation for a pattern signal."""
    signal = pattern_result["signal"]

    if signal == "Bullish":
        return {"score": 15, "bias": "Bullish"}

    if signal == "Bearish":
        return {"score": 15, "bias": "Bearish"}

    return {"score": 5, "bias": "Neutral"}
