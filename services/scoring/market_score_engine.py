"""
Market Score Engine

Calculates the overall market quality score.
"""


def calculate_market_score(
    trend,
    structure,
    smart_money,
):
    """
    Returns
    -------
    dict
    """

    score = 0

    # Trend (40)

    if trend["signal"] == "BULLISH":
        score += 40

    elif trend["signal"] == "BEARISH":
        score += 40

    # Structure (30)

    if structure["signal"] in (
        "UPTREND",
        "DOWNTREND",
    ):
        score += 30

    # Smart Money (30)

    if smart_money["signal"] == "STRONG":
        score += 30

    elif smart_money["signal"] == "MODERATE":
        score += 15

    grade = (
        "A"
        if score >= 90
        else "B"
        if score >= 75
        else "C"
        if score >= 60
        else "D"
    )

    return {
        "score": score,
        "grade": grade,
    }