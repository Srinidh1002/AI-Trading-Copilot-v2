"""
ADX Engine

Calculates Average Directional Index (ADX).
"""

import pandas as pd


def calculate_adx(
    df: pd.DataFrame,
    period: int = 14,
):
    """
    Calculate ADX.

    Returns
    -------
    dict
    """

    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where(
        (plus_dm > minus_dm) & (plus_dm > 0),
        0,
    )

    minus_dm = minus_dm.where(
        (minus_dm > plus_dm) & (minus_dm > 0),
        0,
    )

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    plus_di = 100 * (
        plus_dm.rolling(period).mean() / atr
    )

    minus_di = 100 * (
        minus_dm.rolling(period).mean() / atr
    )

    dx = (
        (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, 1e-10)
    ) * 100

    adx = dx.rolling(period).mean()

    value = float(adx.iloc[-1])

    if value >= 25:
        strength = "STRONG"
    elif value >= 20:
        strength = "MODERATE"
    else:
        strength = "WEAK"

    return {
        "adx": value,
        "strength": strength,
    }