"""
ATR Engine

Calculates Average True Range (ATR).
"""

import pandas as pd


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14,
):
    """
    Calculate ATR.

    Returns
    -------
    dict
    """

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    value = float(atr.iloc[-1])

    avg_price = float(close.iloc[-1])

    volatility = (value / avg_price) * 100

    if volatility > 2:
        level = "HIGH"
    elif volatility > 1:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "atr": value,
        "volatility": volatility,
        "level": level,
    }