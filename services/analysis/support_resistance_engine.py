"""
Support / Resistance Engine

Detects the nearest support and resistance levels.
"""

import pandas as pd


def analyze_support_resistance(snapshot, lookback=50):
    """
    Returns nearest support and resistance.
    """

    df: pd.DataFrame = snapshot["history"]

    recent = df.tail(lookback)

    current = float(df.iloc[-1]["close"])

    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    distance_to_support = current - support
    distance_to_resistance = resistance - current

    if distance_to_support < distance_to_resistance:
        signal = "SUPPORT"

    elif distance_to_resistance < distance_to_support:
        signal = "RESISTANCE"

    else:
        signal = "NEUTRAL"

    total_range = max(resistance - support, 0.01)

    confidence = round(
        min(
            100,
            (1 - min(distance_to_support, distance_to_resistance) / total_range)
            * 100,
        ),
        2,
    )

    return {
        "signal": signal,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "distance_to_support": round(distance_to_support, 2),
        "distance_to_resistance": round(distance_to_resistance, 2),
        "confidence": confidence,
        "reason": (
            "Price near support."
            if signal == "SUPPORT"
            else "Price near resistance."
            if signal == "RESISTANCE"
            else "Price between key levels."
        ),
    }