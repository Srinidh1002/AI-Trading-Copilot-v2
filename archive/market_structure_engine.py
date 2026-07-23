"""
Market Structure Engine

Detects Higher Highs, Higher Lows,
Lower Highs and Lower Lows.
"""

import pandas as pd


def analyze_market_structure(snapshot, lookback=20):
    """
    Analyze market structure.
    """

    df: pd.DataFrame = snapshot["history"]

    recent = df.tail(lookback)

    highs = recent["high"].tolist()
    lows = recent["low"].tolist()

    if len(highs) < 3 or len(lows) < 3:
        return {
            "signal": "RANGE",
            "higher_high": False,
            "higher_low": False,
            "lower_high": False,
            "lower_low": False,
            "confidence": 50,
            "reason": "Insufficient data.",
        }

    higher_high = highs[-1] > highs[-2] > highs[-3]
    higher_low = lows[-1] > lows[-2] > lows[-3]

    lower_high = highs[-1] < highs[-2] < highs[-3]
    lower_low = lows[-1] < lows[-2] < lows[-3]

    if higher_high and higher_low:
        signal = "UPTREND"
        confidence = 90
        reason = "Higher Highs / Higher Lows"

    elif lower_high and lower_low:
        signal = "DOWNTREND"
        confidence = 90
        reason = "Lower Highs / Lower Lows"

    else:
        signal = "RANGE"
        confidence = 60
        reason = "Sideways Market"

    return {
        "signal": signal,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "lower_low": lower_low,
        "confidence": confidence,
        "reason": reason,
    }