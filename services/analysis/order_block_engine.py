"""
Order Block Engine V1
"""

import pandas as pd


def detect_order_blocks(df):

    data = df.reset_index(drop=True)

    bullish = None
    bearish = None

    for i in range(len(data) - 2, 1, -1):

        prev = data.iloc[i - 1]
        curr = data.iloc[i]

        # Bullish Order Block
        if (
            prev["close"] < prev["open"]
            and curr["close"] > prev["high"]
        ):
            bullish = {
                "index": i - 1,
                "high": float(prev["high"]),
                "low": float(prev["low"]),
                "time": str(prev["timestamp"]),
            }
            break

    for i in range(len(data) - 2, 1, -1):

        prev = data.iloc[i - 1]
        curr = data.iloc[i]

        # Bearish Order Block
        if (
            prev["close"] > prev["open"]
            and curr["close"] < prev["low"]
        ):
            bearish = {
                "index": i - 1,
                "high": float(prev["high"]),
                "low": float(prev["low"]),
                "time": str(prev["timestamp"]),
            }
            break

    return {
        "bullish": bullish,
        "bearish": bearish,
    }