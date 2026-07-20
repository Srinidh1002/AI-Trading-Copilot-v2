"""
MACD Engine

Calculates Moving Average Convergence Divergence.
"""

import pandas as pd


def calculate_macd(
    df: pd.DataFrame,
):
    """
    Calculate MACD.

    Returns
    -------
    dict
    """

    close = df["close"]

    ema12 = close.ewm(
        span=12,
        adjust=False,
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False,
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False,
    ).mean()

    histogram = macd - signal

    latest_macd = float(macd.iloc[-1])

    latest_signal = float(signal.iloc[-1])

    latest_histogram = float(histogram.iloc[-1])

    if latest_macd > latest_signal:
        trend = "BULLISH"
    elif latest_macd < latest_signal:
        trend = "BEARISH"
    else:
        trend = "SIDEWAYS"

    return {
        "macd": latest_macd,
        "signal": latest_signal,
        "histogram": latest_histogram,
        "trend": trend,
    }