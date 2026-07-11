"""Technical regime analysis for OHLCV price data."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Literal, TypedDict

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice


Trend = Literal["BULLISH", "BEARISH", "SIDEWAYS"]


class TechnicalIndicators(TypedDict):
    """Latest computed technical-indicator values."""

    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi: float | None
    macd: float | None
    signal: float | None
    vwap: float | None
    atr: float | None


class TechnicalAnalysis(TypedDict):
    """Technical market regime returned by :func:`analyse_technical`."""

    trend: Trend
    score: int
    confidence: int
    indicators: TechnicalIndicators
    reasons: list[str]


_REQUIRED_COLUMNS = {"Open", "High", "Low", "Close", "Volume"}


def _clamp(value: float) -> int:
    """Round a score and bound it to a percentage."""

    return max(0, min(100, round(value)))


def _latest_value(series: pd.Series) -> float | None:
    """Return the final finite value in an indicator series."""

    if series.empty:
        return None

    try:
        value = float(series.iloc[-1])
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _calculate(
    calculation: Callable[[], pd.Series], index: pd.Index
) -> pd.Series:
    """Calculate an indicator, returning aligned NaNs when history is short."""

    try:
        return calculation().reindex(index)
    except (TypeError, ValueError, ZeroDivisionError):
        return pd.Series(float("nan"), index=index, dtype="float64")


def _empty_analysis(reason: str) -> TechnicalAnalysis:
    """Create a neutral analysis when calculation cannot proceed."""

    return {
        "trend": "SIDEWAYS",
        "score": 50,
        "confidence": 0,
        "indicators": {
            "ema20": None,
            "ema50": None,
            "ema200": None,
            "rsi": None,
            "macd": None,
            "signal": None,
            "vwap": None,
            "atr": None,
        },
        "reasons": [reason],
    }


def analyse_technical(df: pd.DataFrame) -> TechnicalAnalysis:
    """Analyse the latest OHLCV bar using EMA, momentum, and volatility data.

    ``score`` is a 0--100 directional score, where 50 is neutral.  Confidence
    reflects the absolute directional score, discounted when requested
    indicators are unavailable because the input history is too short.

    Args:
        df: A pandas DataFrame containing Open, High, Low, Close, and Volume.

    Returns:
        A technical regime, indicator values from the latest row, and the
        signals that contributed to it.

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
        ValueError: If required OHLCV columns are absent.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    missing_columns = _REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required OHLCV columns: {missing}")
    if df.empty:
        return _empty_analysis("No OHLCV data is available.")

    index = df.index
    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    close = pd.to_numeric(df["Close"], errors="coerce")
    volume = pd.to_numeric(df["Volume"], errors="coerce")

    ema20 = _calculate(lambda: EMAIndicator(close, window=20).ema_indicator(), index)
    ema50 = _calculate(lambda: EMAIndicator(close, window=50).ema_indicator(), index)
    ema200 = _calculate(lambda: EMAIndicator(close, window=200).ema_indicator(), index)
    rsi = _calculate(lambda: RSIIndicator(close, window=14).rsi(), index)
    macd_indicator = MACD(close)
    macd = _calculate(macd_indicator.macd, index)
    signal = _calculate(macd_indicator.macd_signal, index)
    vwap = _calculate(
        lambda: VolumeWeightedAveragePrice(
            high, low, close, volume, window=14
        ).volume_weighted_average_price(),
        index,
    )
    atr = _calculate(
        lambda: AverageTrueRange(high, low, close, window=14).average_true_range(),
        index,
    )

    indicators: TechnicalIndicators = {
        "ema20": _latest_value(ema20),
        "ema50": _latest_value(ema50),
        "ema200": _latest_value(ema200),
        "rsi": _latest_value(rsi),
        "macd": _latest_value(macd),
        "signal": _latest_value(signal),
        "vwap": _latest_value(vwap),
        "atr": _latest_value(atr),
    }
    latest_close = _latest_value(close)
    reasons: list[str] = []
    direction = 0
    available_signals = 0

    def add_signal(condition: bool | None, weight: int, bullish: str, bearish: str) -> None:
        """Apply a weighted directional signal when its inputs are available."""

        nonlocal direction, available_signals
        if condition is None:
            return
        available_signals += 1
        if condition:
            direction += weight
            reasons.append(bullish)
        else:
            direction -= weight
            reasons.append(bearish)

    def comparison(left: float | None, right: float | None) -> bool | None:
        """Compare two finite indicator values, retaining missing-data state."""

        return None if left is None or right is None else left > right

    add_signal(
        comparison(latest_close, indicators["ema20"]),
        10,
        "Close is above EMA20.",
        "Close is below EMA20.",
    )
    add_signal(
        comparison(indicators["ema20"], indicators["ema50"]),
        15,
        "EMA20 is above EMA50.",
        "EMA20 is below EMA50.",
    )
    add_signal(
        comparison(indicators["ema50"], indicators["ema200"]),
        20,
        "EMA50 is above EMA200.",
        "EMA50 is below EMA200.",
    )
    add_signal(
        comparison(indicators["macd"], indicators["signal"]),
        15,
        "MACD is above its signal line.",
        "MACD is below its signal line.",
    )
    add_signal(
        comparison(latest_close, indicators["vwap"]),
        10,
        "Close is above VWAP.",
        "Close is below VWAP.",
    )

    rsi_value = indicators["rsi"]
    if rsi_value is not None:
        available_signals += 1
        if rsi_value >= 55:
            direction += 10
            reasons.append(f"RSI is bullish at {rsi_value:.1f}.")
        elif rsi_value <= 45:
            direction -= 10
            reasons.append(f"RSI is bearish at {rsi_value:.1f}.")
        else:
            reasons.append(f"RSI is neutral at {rsi_value:.1f}.")

    if available_signals == 0:
        reasons.append("Insufficient valid history to determine a technical trend.")

    trend: Trend = "SIDEWAYS"
    if direction >= 20:
        trend = "BULLISH"
    elif direction <= -20:
        trend = "BEARISH"

    return {
        "trend": trend,
        "score": _clamp(50 + direction),
        "confidence": _clamp((abs(direction) / 80) * 100 * (available_signals / 6)),
        "indicators": indicators,
        "reasons": reasons,
    }
