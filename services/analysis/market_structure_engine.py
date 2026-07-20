"""
Market Structure Engine

Detects Higher Highs, Higher Lows,
Lower Highs and Lower Lows.
"""

import pandas as pd


def analyze_market_structure(snapshot, lookback=20):
    """
    Analyze market structure.

    Returns
    -------
    dict
    """

    df: pd.DataFrame = snapshot["history"]

    recent = df.tail(lookback)

    highs = recent["high"].tolist()
    lows = recent["low"].tolist()

    higher_high = highs[-1] > highs[-2]
    higher_low = lows[-1] > lows[-2]

    lower_high = highs[-1] < highs[-2]
    lower_low = lows[-1] < lows[-2]

    if higher_high and higher_low:
        structure = "UPTREND"

    elif lower_high and lower_low:
        structure = "DOWNTREND"

    else:
        structure = "RANGE"

    return {
        "signal": structure,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "lower_low": lower_low,
        "confidence": 80,
        "reason": f"Detected {structure} market structure.",
    }