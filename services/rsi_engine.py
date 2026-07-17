"""
RSI Engine V1
"""

import pandas as pd


def calculate_rsi(df, period=14):

    data = df.copy()

    delta = data["Close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    data["RSI"] = 100 - (100 / (1 + rs))

    return float(data["RSI"].iloc[-1])