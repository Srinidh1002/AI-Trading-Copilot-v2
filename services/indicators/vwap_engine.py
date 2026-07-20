"""
VWAP Engine

Calculates Volume Weighted Average Price (VWAP).
"""

import pandas as pd


def calculate_vwap(
    df: pd.DataFrame,
):
    """
    Calculate VWAP.

    Returns
    -------
    dict
    """

    typical_price = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3

    cumulative_tp_volume = (
        typical_price * df["volume"]
    ).cumsum()

    cumulative_volume = df["volume"].cumsum()

    vwap = cumulative_tp_volume / cumulative_volume

    latest_vwap = float(vwap.iloc[-1])
    latest_close = float(df["close"].iloc[-1])

    if latest_close > latest_vwap:
        trend = "ABOVE_VWAP"
    elif latest_close < latest_vwap:
        trend = "BELOW_VWAP"
    else:
        trend = "AT_VWAP"

    return {
        "vwap": latest_vwap,
        "trend": trend,
    }