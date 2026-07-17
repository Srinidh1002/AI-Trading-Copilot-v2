"""
ADX Engine V1
"""

import pandas as pd


def calculate_adx(df, period=14):

    data = df.copy()

    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    # ==========================
    # True Range
    # ==========================

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    # ==========================
    # Directional Movement
    # ==========================

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0),
        0,
    )

    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0),
        0,
    )

    plus_di = (
        100 *
        (plus_dm.rolling(period).mean() / atr)
    )

    minus_di = (
        100 *
        (minus_dm.rolling(period).mean() / atr)
    )

    dx = (
        ((plus_di - minus_di).abs()) /
        (plus_di + minus_di)
    ) * 100

    adx = dx.rolling(period).mean()

    value = float(adx.iloc[-1])

    if value >= 40:
        strength = "Very Strong"

    elif value >= 25:
        strength = "Strong"

    elif value >= 20:
        strength = "Moderate"

    else:
        strength = "Weak"

    return {
        "ADX": value,
        "Strength": strength,
    }