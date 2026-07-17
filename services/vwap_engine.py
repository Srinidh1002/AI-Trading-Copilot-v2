"""
VWAP Engine V1
"""

import pandas as pd


def calculate_vwap(df):

    data = df.copy()
    data = data.dropna(subset=["High", "Low", "Close", "Volume"])
    if data["Volume"].sum() == 0:
     return {
        "VWAP": None,
        "Trend": "Unavailable"
    }

    typical_price = (
        data["High"] +
        data["Low"] +
        data["Close"]
    ) / 3

    vwap = (
        (typical_price * data["Volume"]).cumsum() /
        data["Volume"].cumsum()
    )

    value = float(vwap.dropna().iloc[-1])

    if data["Close"].iloc[-1] > value:
        trend = "Bullish"
    else:
        trend = "Bearish"

    return {
        "VWAP": value,
        "Trend": trend
    }