"""
Build indicators required by the market-regime engine.
"""

import pandas as pd


def add_regime_indicators(data: pd.DataFrame) -> pd.DataFrame:
    required = {
        "High",
        "Low",
        "Close",
    }

    if data is None or data.empty:
        raise ValueError("No market data provided.")

    missing = required - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = data.copy()

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    # EMA
    df["EMA20"] = close.ewm(
        span=20,
        adjust=False,
    ).mean()

    df["EMA50"] = close.ewm(
        span=50,
        adjust=False,
    ).mean()

    # ATR
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["ATR"] = true_range.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    # ADX
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where(
        (up_move > down_move)
        & (up_move > 0),
        0.0,
    )

    minus_dm = down_move.where(
        (down_move > up_move)
        & (down_move > 0),
        0.0,
    )

    atr = df["ATR"].replace(0, float("nan"))

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
        ).mean()
        / atr
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
        ).mean()
        / atr
    )

    denominator = (
        plus_di + minus_di
    ).replace(
        0,
        float("nan"),
    )

    dx = (
        100
        * (
            plus_di - minus_di
        ).abs()
        / denominator
    )

    df["ADX"] = dx.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean().fillna(0)

    # Bollinger Bands
    middle = close.rolling(
        window=20,
        min_periods=1,
    ).mean()

    std = close.rolling(
        window=20,
        min_periods=1,
    ).std(
        ddof=0
    ).fillna(0)

    df["BB_UPPER"] = (
        middle + 2 * std
    )

    df["BB_LOWER"] = (
        middle - 2 * std
    )

    return df