"""
Swing Detection Engine V1
"""

import pandas as pd


def detect_swings(df, lookback=2):

    data = df.reset_index(drop=True)

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(data) - lookback):

        high = data.loc[i, "high"]
        low = data.loc[i, "low"]

        if all(high > data.loc[i-j, "high"] for j in range(1, lookback+1)) and \
           all(high > data.loc[i+j, "high"] for j in range(1, lookback+1)):
            swing_highs.append((i, high))

        if all(low < data.loc[i-j, "low"] for j in range(1, lookback+1)) and \
           all(low < data.loc[i+j, "low"] for j in range(1, lookback+1)):
            swing_lows.append((i, low))

    last_high = swing_highs[-1][1] if swing_highs else None
    prev_high = swing_highs[-2][1] if len(swing_highs) >= 2 else None

    last_low = swing_lows[-1][1] if swing_lows else None
    prev_low = swing_lows[-2][1] if len(swing_lows) >= 2 else None

    trend = "Neutral"

    if (
        last_high is not None
        and prev_high is not None
        and last_low is not None
        and prev_low is not None
    ):
        if last_high > prev_high and last_low > prev_low:
            trend = "Bullish"
        elif last_high < prev_high and last_low < prev_low:
            trend = "Bearish"

    return {
        "last_swing_high": last_high,
        "previous_swing_high": prev_high,
        "last_swing_low": last_low,
        "previous_swing_low": prev_low,
        "trend": trend,
    }