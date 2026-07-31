"""Build indicators required by the market-regime engine.

The public analysis pipeline uses canonical uppercase OHLCV columns.
This builder preserves that schema while adding regime indicators.
"""

from __future__ import annotations

import pandas as pd


_REQUIRED_COLUMNS = {
    "High",
    "Low",
    "Close",
}


def _validate_input(data: object) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "data must be a pandas DataFrame"
        )

    if data.empty:
        raise ValueError(
            "No market data provided."
        )

    missing = _REQUIRED_COLUMNS.difference(
        data.columns
    )

    if missing:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing)}"
        )

    return data.copy()


def _numeric_series(
    data: pd.DataFrame,
    column: str,
) -> pd.Series:
    result = pd.to_numeric(
        data[column],
        errors="coerce",
    )

    if result.isna().all():
        raise ValueError(
            f"{column} contains no valid numeric values"
        )

    return result.astype(float)


def add_regime_indicators(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Add EMA, ATR, ADX, and Bollinger indicators.

    The input and returned DataFrames preserve the uppercase
    ``High``, ``Low``, and ``Close`` columns expected by the
    downstream market-regime analyzer.
    """

    df = _validate_input(data)

    high = _numeric_series(
        df,
        "High",
    )
    low = _numeric_series(
        df,
        "Low",
    )
    close = _numeric_series(
        df,
        "Close",
    )

    valid_ohlc = (
        high.notna()
        & low.notna()
        & close.notna()
    )

    if not valid_ohlc.any():
        raise ValueError(
            "No rows contain valid High, Low, and Close values"
        )

    df["High"] = high
    df["Low"] = low
    df["Close"] = close

    # Exponential moving averages
    df["EMA20"] = close.ewm(
        span=20,
        adjust=False,
        min_periods=1,
    ).mean()

    df["EMA50"] = close.ewm(
        span=50,
        adjust=False,
        min_periods=1,
    ).mean()

    # Average True Range
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
        min_periods=1,
    ).mean()

    # Directional movement
    upward_move = high.diff()
    downward_move = -low.diff()

    plus_dm = upward_move.where(
        (upward_move > downward_move)
        & (upward_move > 0),
        0.0,
    )

    minus_dm = downward_move.where(
        (downward_move > upward_move)
        & (downward_move > 0),
        0.0,
    )

    atr_denominator = df["ATR"].replace(
        0,
        float("nan"),
    )

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=1,
        ).mean()
        / atr_denominator
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=1,
        ).mean()
        / atr_denominator
    )

    directional_denominator = (
        plus_di + minus_di
    ).replace(
        0,
        float("nan"),
    )

    directional_index = (
        100
        * (plus_di - minus_di).abs()
        / directional_denominator
    )

    df["ADX"] = directional_index.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=1,
    ).mean().fillna(0.0)

    # Bollinger Bands
    middle_band = close.rolling(
        window=20,
        min_periods=1,
    ).mean()

    standard_deviation = close.rolling(
        window=20,
        min_periods=1,
    ).std(
        ddof=0
    ).fillna(0.0)

    df["BB_UPPER"] = (
        middle_band
        + 2 * standard_deviation
    )

    df["BB_LOWER"] = (
        middle_band
        - 2 * standard_deviation
    )

    return df