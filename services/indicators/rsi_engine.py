"""
RSI Engine

Calculates Relative Strength Index (RSI).
"""

import pandas as pd


def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
):
    """
    Calculate RSI.

    Returns
    -------
    float
    """

    delta = df["close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)

    rsi = 100 - (100 / (1 + rs))

    return float(rsi.iloc[-1])