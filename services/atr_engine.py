"""
ATR Engine V1
"""

import pandas as pd


def calculate_atr(df, period=14):

    data = df.copy()

    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    value = float(atr.iloc[-1])

    if value >= 100:
        volatility = "High"
    elif value >= 50:
        volatility = "Moderate"
    else:
        volatility = "Low"

    return {
        "ATR": value,
        "Volatility": volatility
    }