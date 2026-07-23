"""
Smart Money Engine

Combines multiple Smart Money Concept (SMC) signals.
"""


def analyze_smart_money(snapshot):
    """
    Analyze Smart Money Concepts.

    Returns
    -------
    dict
    """

    score = 0
    reasons = []

    if snapshot.get("order_blocks"):
        score += 2
        reasons.append("Order Block")

    if snapshot.get("fair_value_gaps"):
        score += 2
        reasons.append("Fair Value Gap")

    if snapshot.get("supply_demand"):
        score += 2
        reasons.append("Supply / Demand")

    if snapshot.get("bos"):
        score += 2
        reasons.append("Break of Structure")

    if snapshot.get("choch"):
        score += 2
        reasons.append("Change of Character")

    if score >= 8:
        signal = "STRONG"

    elif score >= 5:
        signal = "MODERATE"

    else:
        signal = "WEAK"

    return {
        "signal": signal,
        "score": score,
        "confidence": min(score * 10, 100),
        "reason": ", ".join(reasons),
    }