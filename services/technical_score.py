"""Convert technical-indicator values into bullish and bearish scores."""

import math

import pandas as pd


def _latest_number(row: pd.Series, column: str) -> float | None:
    """Return a finite numeric value from a row, or ``None`` when unavailable."""
    try:
        value = row.get(column)
        if pd.isna(value):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _has_values(*values: float | None) -> bool:
    """Return whether every supplied indicator value is available."""
    return all(value is not None for value in values)


def technical_score(df: pd.DataFrame) -> dict[str, int | list[str]]:
    """Score the latest technical-indicator row as bullish and bearish.

    Missing columns, empty input, and unavailable indicator values are treated as
    neutral signals so callers always receive a usable score dictionary.

    Args:
        df: Market data containing the required technical-indicator columns.

    Returns:
        A dictionary with integer ``bull`` and ``bear`` scores plus readable
        ``signals`` describing the conditions that contributed to them.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"bull": 0, "bear": 0, "signals": []}

    row = df.iloc[-1]
    signals: list[str] = []
    bull = 0
    bear = 0

    close = _latest_number(row, "Close")
    ema20 = _latest_number(row, "EMA20")
    ema50 = _latest_number(row, "EMA50")
    ema200 = _latest_number(row, "EMA200")
    rsi = _latest_number(row, "RSI")
    macd = _latest_number(row, "MACD")
    macd_signal = _latest_number(row, "MACD_SIGNAL")
    adx = _latest_number(row, "ADX")
    vwap = _latest_number(row, "VWAP")
    bb_upper = _latest_number(row, "BB_UPPER")
    bb_lower = _latest_number(row, "BB_LOWER")

    if _has_values(close, ema20):
        if close > ema20:
            bull += 5
            signals.append("Price above EMA20")
        elif close < ema20:
            bear += 5
            signals.append("Price below EMA20")

    if _has_values(ema20, ema50):
        if ema20 > ema50:
            bull += 10
            signals.append("EMA20 above EMA50")
        elif ema20 < ema50:
            bear += 10
            signals.append("EMA20 below EMA50")

    if _has_values(ema50, ema200):
        if ema50 > ema200:
            bull += 10
            signals.append("EMA50 above EMA200")
        elif ema50 < ema200:
            bear += 10
            signals.append("EMA50 below EMA200")

    if rsi is not None:
        if rsi < 30:
            bull += 15
            signals.append("Oversold RSI")
        elif rsi > 70:
            bear += 15
            signals.append("Overbought RSI")

    if _has_values(macd, macd_signal):
        if macd > macd_signal:
            bull += 15
            signals.append("Bullish MACD crossover")
        else:
            bear += 15
            signals.append("Bearish MACD crossover")

    if _has_values(close, vwap):
        if close > vwap:
            bull += 10
            signals.append("Above VWAP")
        else:
            bear += 10
            signals.append("Below VWAP")

    if _has_values(close, bb_lower) and close < bb_lower:
        bull += 10
        signals.append("Near lower Bollinger Band")

    if _has_values(close, bb_upper) and close > bb_upper:
        bear += 10
        signals.append("Near upper Bollinger Band")

    if adx is not None and adx > 25:
        bull += 5
        bear += 5
        signals.append("Strong trend (ADX above 25)")

    return {"bull": bull, "bear": bear, "signals": signals}
