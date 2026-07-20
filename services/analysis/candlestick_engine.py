"""
Candlestick Pattern Engine

Recognizes common candlestick patterns.
"""

import pandas as pd

from services.candlestick_engine import detect_pattern


def analyze_candlestick(snapshot):
    """
    Detect candlestick patterns.

    Returns
    -------
    dict
    """

    df: pd.DataFrame = snapshot["history"]

    candle = df.iloc[-1]

    open_price = float(candle["open"])
    close_price = float(candle["close"])
    high = float(candle["high"])
    low = float(candle["low"])

    body = abs(close_price - open_price)
    upper = high - max(open_price, close_price)
    lower = min(open_price, close_price) - low

    pattern = "NONE"

    if body < (high - low) * 0.1:
        pattern = "DOJI"

    elif lower > body * 2:
        pattern = "HAMMER"

    elif upper > body * 2:
        pattern = "SHOOTING_STAR"

    elif close_price > open_price:
        pattern = "BULLISH"

    elif close_price < open_price:
        pattern = "BEARISH"

    return {
        "signal": pattern,
        "confidence": 70,
        "reason": f"Detected {pattern} candlestick.",
    }
