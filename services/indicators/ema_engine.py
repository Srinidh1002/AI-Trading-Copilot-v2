"""
EMA Engine

Calculates Exponential Moving Averages.
"""

import pandas as pd


def calculate_ema(
    df: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
):
    """
    Calculate EMA values.

    Returns
    -------
    dict
    """

    close = df["close"]

    ema_fast = close.ewm(
        span=fast_period,
        adjust=False,
    ).mean()

    ema_slow = close.ewm(
        span=slow_period,
        adjust=False,
    ).mean()

    latest_fast = float(ema_fast.iloc[-1])
    latest_slow = float(ema_slow.iloc[-1])

    if latest_fast > latest_slow:
        trend = "BULLISH"
    elif latest_fast < latest_slow:
        trend = "BEARISH"
    else:
        trend = "SIDEWAYS"

    return {
        "ema20": latest_fast,
        "ema50": latest_slow,
        "trend": trend,
    }