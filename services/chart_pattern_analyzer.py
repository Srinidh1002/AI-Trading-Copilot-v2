"""
Advanced chart-pattern recognition engine.

Detects:
- Double top
- Double bottom
- Uptrend structure
- Downtrend structure
- Consolidation
- Price compression
- Breakout / breakdown
- Volume confirmation
"""

import pandas as pd


def analyse_chart_patterns(data: pd.DataFrame) -> dict:
    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    default_result = {
        "patterns": [],
        "signal": "NEUTRAL",
        "score": 0,
        "volume_confirmation": False,
    }

    if data is None or data.empty:
        return default_result

    missing = required_columns - set(data.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = data.copy().reset_index(drop=True)

    if len(df) < 5:
        return default_result

    patterns = []
    score = 0

    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    volumes = df["volume"].astype(float)

    # ---------------------------------
    # MARKET STRUCTURE
    # ---------------------------------

    recent = df.tail(5)

    recent_highs = recent["high"].astype(float).tolist()
    recent_lows = recent["low"].astype(float).tolist()

    higher_highs = all(
        recent_highs[i] > recent_highs[i - 1]
        for i in range(1, len(recent_highs))
    )

    higher_lows = all(
        recent_lows[i] > recent_lows[i - 1]
        for i in range(1, len(recent_lows))
    )

    lower_highs = all(
        recent_highs[i] < recent_highs[i - 1]
        for i in range(1, len(recent_highs))
    )

    lower_lows = all(
        recent_lows[i] < recent_lows[i - 1]
        for i in range(1, len(recent_lows))
    )

    if higher_highs and higher_lows:
        patterns.append("UPTREND_STRUCTURE")
        score += 2

    elif lower_highs and lower_lows:
        patterns.append("DOWNTREND_STRUCTURE")
        score -= 2

    # ---------------------------------
    # DOUBLE TOP / DOUBLE BOTTOM
    # ---------------------------------

    lookback = min(20, len(df))
    window = df.tail(lookback)

    max_high = float(window["high"].max())
    min_low = float(window["low"].min())

    tolerance = 0.005  # 0.5%

    high_matches = window[
        abs(window["high"] - max_high) / max_high <= tolerance
    ]

    if len(high_matches) >= 2:
        positions = high_matches.index.tolist()

        if positions[-1] - positions[0] >= 2:
            patterns.append("DOUBLE_TOP")
            score -= 2

    if min_low != 0:
        low_matches = window[
            abs(window["low"] - min_low) / abs(min_low)
            <= tolerance
        ]

        if len(low_matches) >= 2:
            positions = low_matches.index.tolist()

            if positions[-1] - positions[0] >= 2:
                patterns.append("DOUBLE_BOTTOM")
                score += 2

    # ---------------------------------
    # CONSOLIDATION
    # ---------------------------------

    recent_window = df.tail(min(10, len(df)))

    highest = float(recent_window["high"].max())
    lowest = float(recent_window["low"].min())

    average_price = float(
        recent_window["close"].mean()
    )

    if average_price != 0:
        range_percent = (
            (highest - lowest) / average_price
        )

        if range_percent <= 0.03:
            patterns.append("CONSOLIDATION")

    # ---------------------------------
    # PRICE COMPRESSION
    # ---------------------------------

    candle_ranges = (
        highs - lows
    ).tail(5).tolist()

    if len(candle_ranges) >= 5:
        shrinking_ranges = all(
            candle_ranges[i] <= candle_ranges[i - 1]
            for i in range(1, len(candle_ranges))
        )

        if shrinking_ranges:
            patterns.append("PRICE_COMPRESSION")

    # ---------------------------------
    # BREAKOUT / BREAKDOWN
    # ---------------------------------

    if len(df) >= 6:
        previous = df.iloc[-6:-1]

        previous_resistance = float(
            previous["high"].max()
        )

        previous_support = float(
            previous["low"].min()
        )

        latest_close = float(
            df.iloc[-1]["close"]
        )

        if latest_close > previous_resistance:
            patterns.append("BREAKOUT")
            score += 3

        elif latest_close < previous_support:
            patterns.append("BREAKDOWN")
            score -= 3

    # ---------------------------------
    # VOLUME CONFIRMATION
    # ---------------------------------

    volume_confirmation = False

    if len(df) >= 6:
        previous_average_volume = float(
            volumes.iloc[-6:-1].mean()
        )

        latest_volume = float(
            volumes.iloc[-1]
        )

        if (
            previous_average_volume > 0
            and latest_volume
            >= previous_average_volume * 1.5
        ):
            volume_confirmation = True
            patterns.append("HIGH_VOLUME_CONFIRMATION")

            if "BREAKOUT" in patterns:
                score += 2

            elif "BREAKDOWN" in patterns:
                score -= 2

    # ---------------------------------
    # FINAL SIGNAL
    # ---------------------------------

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
        "volume_confirmation": volume_confirmation,
    }