"""Technical indicator calculations for OHLCV market data."""

from collections.abc import Callable

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice


def _empty_indicator(index: pd.Index) -> pd.Series:
    """Create an all-NaN indicator series aligned to *index*."""
    return pd.Series(float("nan"), index=index, dtype="float64")


def _safe_indicator(
    calculation: Callable[[], pd.Series], index: pd.Index
) -> pd.Series:
    """Run an indicator calculation, returning NaNs when history is insufficient."""
    try:
        return calculation().reindex(index)
    except Exception:
        # Some ta indicators require a minimum number of rows before calculating.
        return _empty_indicator(index)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add common technical indicators to an OHLCV data frame.

    The input index is preserved.  Indicators that cannot be calculated because
    the history is too short are returned as ``NaN`` instead of raising errors.

    Args:
        df: Data frame containing Open, High, Low, Close, and Volume columns.

    Returns:
        A copy of ``df`` with technical-indicator columns added.

    Raises:
        ValueError: If one or more required OHLCV columns are missing.
    """
    required_columns = {"Open", "High", "Low", "Close", "Volume"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required OHLCV columns: {missing}")

    result = df.copy()
    index = result.index

    high = pd.to_numeric(result["High"], errors="coerce")
    low = pd.to_numeric(result["Low"], errors="coerce")
    close = pd.to_numeric(result["Close"], errors="coerce")
    volume = pd.to_numeric(result["Volume"], errors="coerce")

    result["EMA20"] = _safe_indicator(
        lambda: EMAIndicator(close=close, window=20).ema_indicator(), index
    )
    result["EMA50"] = _safe_indicator(
        lambda: EMAIndicator(close=close, window=50).ema_indicator(), index
    )
    result["EMA200"] = _safe_indicator(
        lambda: EMAIndicator(close=close, window=200).ema_indicator(), index
    )
    result["RSI"] = _safe_indicator(
        lambda: RSIIndicator(close=close, window=14).rsi(), index
    )

    result["MACD"] = _safe_indicator(
        lambda: MACD(close=close).macd(), index
    )
    result["MACD_SIGNAL"] = _safe_indicator(
        lambda: MACD(close=close).macd_signal(), index
    )
    result["MACD_HIST"] = _safe_indicator(
        lambda: MACD(close=close).macd_diff(), index
    )

    result["ADX"] = _safe_indicator(
        lambda: ADXIndicator(high=high, low=low, close=close, window=14).adx(),
        index,
    )
    result["ATR"] = _safe_indicator(
        lambda: AverageTrueRange(
            high=high, low=low, close=close, window=14
        ).average_true_range(),
        index,
    )
    result["VWAP"] = _safe_indicator(
        lambda: VolumeWeightedAveragePrice(
            high=high, low=low, close=close, volume=volume, window=14
        ).volume_weighted_average_price(),
        index,
    )

    result["BB_UPPER"] = _safe_indicator(
        lambda: BollingerBands(
            close=close, window=20, window_dev=2
        ).bollinger_hband(),
        index,
    )
    result["BB_MIDDLE"] = _safe_indicator(
        lambda: BollingerBands(
            close=close, window=20, window_dev=2
        ).bollinger_mavg(),
        index,
    )
    result["BB_LOWER"] = _safe_indicator(
        lambda: BollingerBands(
            close=close, window=20, window_dev=2
        ).bollinger_lband(),
        index,
    )

    return result
