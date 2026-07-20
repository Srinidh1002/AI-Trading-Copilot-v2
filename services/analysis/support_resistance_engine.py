"""
Support / Resistance Engine

Detects the nearest support and resistance levels.
"""

import pandas as pd


def analyze_support_resistance(
    snapshot,
    lookback=50,
):
    """
    Returns nearest support and resistance.
    """

    df: pd.DataFrame = snapshot["history"]

    recent = df.tail(lookback)

    support = float(recent["low"].min())

    resistance = float(recent["high"].max())

    current = float(df.iloc[-1]["close"])

    return {
        "signal": "NEUTRAL",
        "support": support,
        "resistance": resistance,
        "distance_to_support": round(current - support, 2),
        "distance_to_resistance": round(resistance - current, 2),
        "confidence": 70,
        "reason": "Support and resistance calculated from recent price action.",
    }