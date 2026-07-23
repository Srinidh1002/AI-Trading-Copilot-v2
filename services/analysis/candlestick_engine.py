"""
Candlestick Pattern Analysis Engine
"""

import pandas as pd

from services.candlestick_engine import detect_pattern


def analyze_candlestick(snapshot):
    """
    Analyze latest candlestick using Pattern Engine V2.
    """

    df: pd.DataFrame = snapshot["history"]

    result = detect_pattern(df)

    signal_map = {
        "BUY": "BULLISH",
        "SELL": "BEARISH",
        "HOLD": "NEUTRAL",
    }

    return {
        "signal": signal_map.get(result["signal"], "NEUTRAL"),
        "pattern": result["pattern"],
        "score": result["score"],
        "confidence": result["confidence"],
        "reason": result["reason"],
    }