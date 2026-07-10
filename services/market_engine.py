"""Overall market-trend analysis using index price data."""

from typing import TypeAlias

import pandas as pd
import yfinance as yf

from services.technical import calculate_indicators


MarketScore: TypeAlias = dict[str, str | int]


def _fallback_result() -> MarketScore:
    """Return the standard response used when market data is unavailable."""
    return {
        "trend": "Neutral",
        "confidence": 50,
        "reason": "Unable to retrieve market data",
    }


def _normalise_ohlcv_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance's single-symbol multi-index columns when present."""
    if not isinstance(data.columns, pd.MultiIndex):
        return data

    required = {"Open", "High", "Low", "Close", "Volume"}
    for level in range(data.columns.nlevels):
        level_values = data.columns.get_level_values(level)
        if required.issubset(set(level_values)):
            normalised = data.copy()
            normalised.columns = level_values
            return normalised

    return data


def _is_greater(left: object, right: object) -> bool:
    """Safely compare two numeric indicator values."""
    try:
        return bool(pd.notna(left) and pd.notna(right) and float(left) > float(right))
    except (TypeError, ValueError):
        return False


def market_score(index: str = "^NSEI") -> MarketScore:
    """Assess an index's recent technical trend.

    The score uses the latest candle in three months of daily history. Any
    download or calculation failure returns a neutral fallback response.

    Args:
        index: Yahoo Finance index symbol, such as ``^NSEI``.

    Returns:
        The market trend, bullish confidence score, and a readable rationale.
    """
    try:
        data = yf.download(index, period="3mo", interval="1d", progress=False)
        if data.empty:
            return _fallback_result()

        indicators = calculate_indicators(_normalise_ohlcv_columns(data))
        if indicators.empty:
            return _fallback_result()

        latest = indicators.iloc[-1]
        confidence = 0
        reasons: list[str] = []

        if _is_greater(latest.get("Close"), latest.get("EMA20")):
            confidence += 20
            reasons.append("Close above EMA20")

        if _is_greater(latest.get("EMA20"), latest.get("EMA50")):
            confidence += 30
            reasons.append("EMA20 above EMA50")

        if _is_greater(latest.get("MACD"), latest.get("MACD_SIGNAL")):
            confidence += 30
            reasons.append("Bullish MACD crossover")

        if _is_greater(latest.get("RSI"), 55):
            confidence += 20
            reasons.append("RSI above 55")

        if confidence >= 80:
            trend = "Bullish"
        elif confidence >= 40:
            trend = "Neutral"
        else:
            trend = "Bearish"

        reason = "; ".join(reasons) if reasons else "No bullish conditions met"
        return {"trend": trend, "confidence": confidence, "reason": reason}
    except Exception:
        return _fallback_result()
