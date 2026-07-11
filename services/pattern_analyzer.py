"""
Pattern recognition engine.

Detects:
- Bullish / bearish engulfing
- Hammer
- Shooting star
- Doji
- Breakouts / breakdowns
- Support and resistance
"""

import pandas as pd


def analyse_patterns(data: pd.DataFrame) -> dict:
    required_columns = {"open", "high", "low", "close"}

    if data is None or data.empty:
        return {
            "patterns": [],
            "signal": "NEUTRAL",
            "score": 0,
            "support": None,
            "resistance": None,
        }

    missing = required_columns - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = data.copy().reset_index(drop=True)

    patterns = []
    score = 0

    latest = df.iloc[-1]

    open_price = float(latest["open"])
    high = float(latest["high"])
    low = float(latest["low"])
    close = float(latest["close"])

    body = abs(close - open_price)
    candle_range = high - low

    # Avoid division by zero
    if candle_range == 0:
        candle_range = 0.000001

    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low

    # -------------------------
    # DOJI
    # -------------------------

    if body <= candle_range * 0.1:
        patterns.append("DOJI")

    # -------------------------
    # HAMMER
    # -------------------------

    if (
        lower_wick >= body * 2
        and upper_wick <= max(body, candle_range * 0.1)
    ):
        patterns.append("HAMMER")
        score += 1

    # -------------------------
    # SHOOTING STAR
    # -------------------------

    if (
        upper_wick >= body * 2
        and lower_wick <= max(body, candle_range * 0.1)
    ):
        patterns.append("SHOOTING_STAR")
        score -= 1

    # -------------------------
    # ENGULFING PATTERNS
    # -------------------------

    if len(df) >= 2:

        previous = df.iloc[-2]

        previous_open = float(previous["open"])
        previous_close = float(previous["close"])

        # Bullish engulfing
        if (
            previous_close < previous_open
            and close > open_price
            and open_price <= previous_close
            and close >= previous_open
        ):
            patterns.append("BULLISH_ENGULFING")
            score += 2

        # Bearish engulfing
        if (
            previous_close > previous_open
            and close < open_price
            and open_price >= previous_close
            and close <= previous_open
        ):
            patterns.append("BEARISH_ENGULFING")
            score -= 2

    # -------------------------
    # SUPPORT / RESISTANCE
    # -------------------------

    lookback = min(20, len(df))

    recent = df.tail(lookback)

    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    # -------------------------
    # BREAKOUT / BREAKDOWN
    # -------------------------

    if len(df) >= 6:

        previous_candles = df.iloc[-6:-1]

        previous_resistance = float(
            previous_candles["high"].max()
        )

        previous_support = float(
            previous_candles["low"].min()
        )

        if close > previous_resistance:
            patterns.append("BULLISH_BREAKOUT")
            score += 3

        elif close < previous_support:
            patterns.append("BEARISH_BREAKDOWN")
            score -= 3

    # -------------------------
    # FINAL SIGNAL
    # -------------------------

    if score >= 2:
        signal = "BULLISH"

    elif score <= -2:
        signal = "BEARISH"

    else:
        signal = "NEUTRAL"

    return {
        "patterns": patterns,
        "signal": signal,
        "score": score,
        "support": support,
        "resistance": resistance,
    }