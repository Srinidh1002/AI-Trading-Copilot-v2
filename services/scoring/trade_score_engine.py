"""
Trade Score Engine

Determines whether a trade should be taken.
"""


def calculate_trade_score(
    decision,
    confidence,
    market_score,
):
    """
    Returns
    -------
    dict
    """

    score = (
        confidence["confidence"] * 0.50
        + market_score["score"] * 0.50
    )

    score = round(score, 2)

    if score >= 90:
        quality = "EXCELLENT"

    elif score >= 80:
        quality = "GOOD"

    elif score >= 70:
        quality = "AVERAGE"

    else:
        quality = "POOR"

    should_trade = score >= 80

    return {
        "score": score,
        "quality": quality,
        "should_trade": should_trade,
        "decision": decision["signal"],
    }