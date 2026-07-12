"""
Advanced chart-pattern recognition engine.

Detects and validates:
- Double top
- Double bottom
- Uptrend structure
- Downtrend structure
- Consolidation
- Price compression
- Breakout / breakdown
- Volume confirmation

Conflicting reversal patterns are resolved before
they are returned to the strategy engine.
"""

import pandas as pd


def _find_swing_highs(
    highs,
):
    """
    Return indexes of local swing highs.
    """

    swing_highs = []

    for index in range(
        1,
        len(highs) - 1,
    ):
        current = highs.iloc[index]

        if (
            current > highs.iloc[index - 1]
            and current >= highs.iloc[index + 1]
        ):
            swing_highs.append(index)

    return swing_highs


def _find_swing_lows(
    lows,
):
    """
    Return indexes of local swing lows.
    """

    swing_lows = []

    for index in range(
        1,
        len(lows) - 1,
    ):
        current = lows.iloc[index]

        if (
            current < lows.iloc[index - 1]
            and current <= lows.iloc[index + 1]
        ):
            swing_lows.append(index)

    return swing_lows


def _find_double_top(
    highs,
    tolerance=0.005,
    minimum_separation=2,
):
    """
    Find the best validated double-top candidate.
    """

    swing_highs = _find_swing_highs(
        highs
    )

    best_candidate = None

    for first_position in range(
        len(swing_highs)
    ):
        for second_position in range(
            first_position + 1,
            len(swing_highs),
        ):
            first_index = swing_highs[
                first_position
            ]

            second_index = swing_highs[
                second_position
            ]

            if (
                second_index - first_index
                < minimum_separation
            ):
                continue

            first_high = float(
                highs.iloc[first_index]
            )

            second_high = float(
                highs.iloc[second_index]
            )

            reference = max(
                abs(first_high),
                abs(second_high),
            )

            if reference == 0:
                continue

            difference_percent = (
                abs(
                    first_high
                    - second_high
                )
                / reference
            )

            if difference_percent > tolerance:
                continue

            quality = (
                1
                - (
                    difference_percent
                    / tolerance
                )
            )

            candidate = {
                "pattern": "DOUBLE_TOP",
                "first_index": first_index,
                "second_index": second_index,
                "recency": second_index,
                "quality": round(
                    quality,
                    4,
                ),
            }

            if (
                best_candidate is None
                or candidate["recency"]
                > best_candidate["recency"]
                or (
                    candidate["recency"]
                    == best_candidate["recency"]
                    and candidate["quality"]
                    > best_candidate["quality"]
                )
            ):
                best_candidate = candidate

    return best_candidate


def _find_double_bottom(
    lows,
    tolerance=0.005,
    minimum_separation=2,
):
    """
    Find the best validated double-bottom candidate.
    """

    swing_lows = _find_swing_lows(
        lows
    )

    best_candidate = None

    for first_position in range(
        len(swing_lows)
    ):
        for second_position in range(
            first_position + 1,
            len(swing_lows),
        ):
            first_index = swing_lows[
                first_position
            ]

            second_index = swing_lows[
                second_position
            ]

            if (
                second_index - first_index
                < minimum_separation
            ):
                continue

            first_low = float(
                lows.iloc[first_index]
            )

            second_low = float(
                lows.iloc[second_index]
            )

            reference = max(
                abs(first_low),
                abs(second_low),
            )

            if reference == 0:
                continue

            difference_percent = (
                abs(
                    first_low
                    - second_low
                )
                / reference
            )

            if difference_percent > tolerance:
                continue

            quality = (
                1
                - (
                    difference_percent
                    / tolerance
                )
            )

            candidate = {
                "pattern": "DOUBLE_BOTTOM",
                "first_index": first_index,
                "second_index": second_index,
                "recency": second_index,
                "quality": round(
                    quality,
                    4,
                ),
            }

            if (
                best_candidate is None
                or candidate["recency"]
                > best_candidate["recency"]
                or (
                    candidate["recency"]
                    == best_candidate["recency"]
                    and candidate["quality"]
                    > best_candidate["quality"]
                )
            ):
                best_candidate = candidate

    return best_candidate


def _resolve_reversal_conflict(
    double_top,
    double_bottom,
):
    """
    Resolve simultaneous double-top and double-bottom
    candidates.

    Priority:
    1. More recent second swing.
    2. Better pattern quality.
    3. If still tied, reject both as unresolved.
    """

    if (
        double_top is None
        and double_bottom is None
    ):
        return None, False

    if double_top is None:
        return double_bottom, False

    if double_bottom is None:
        return double_top, False

    top_recency = double_top[
        "recency"
    ]

    bottom_recency = double_bottom[
        "recency"
    ]

    if top_recency > bottom_recency:
        return double_top, True

    if bottom_recency > top_recency:
        return double_bottom, True

    top_quality = double_top[
        "quality"
    ]

    bottom_quality = double_bottom[
        "quality"
    ]

    if top_quality > bottom_quality:
        return double_top, True

    if bottom_quality > top_quality:
        return double_bottom, True

    return None, True


def analyse_chart_patterns(
    data: pd.DataFrame,
) -> dict:

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
        "pattern_conflict_resolved": False,
    }

    if data is None or data.empty:
        return default_result

    missing = (
        required_columns
        - set(data.columns)
    )

    if missing:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing)}"
        )

    df = (
        data.copy()
        .reset_index(
            drop=True
        )
    )

    if len(df) < 5:
        return default_result

    patterns = []

    score = 0

    closes = (
        df["close"]
        .astype(float)
    )

    highs = (
        df["high"]
        .astype(float)
    )

    lows = (
        df["low"]
        .astype(float)
    )

    volumes = (
        df["volume"]
        .astype(float)
    )

    # ---------------------------------
    # MARKET STRUCTURE
    # ---------------------------------

    recent = df.tail(5)

    recent_highs = (
        recent["high"]
        .astype(float)
        .tolist()
    )

    recent_lows = (
        recent["low"]
        .astype(float)
        .tolist()
    )

    higher_highs = all(
        recent_highs[index]
        > recent_highs[index - 1]
        for index in range(
            1,
            len(recent_highs),
        )
    )

    higher_lows = all(
        recent_lows[index]
        > recent_lows[index - 1]
        for index in range(
            1,
            len(recent_lows),
        )
    )

    lower_highs = all(
        recent_highs[index]
        < recent_highs[index - 1]
        for index in range(
            1,
            len(recent_highs),
        )
    )

    lower_lows = all(
        recent_lows[index]
        < recent_lows[index - 1]
        for index in range(
            1,
            len(recent_lows),
        )
    )

    if (
        higher_highs
        and higher_lows
    ):
        patterns.append(
            "UPTREND_STRUCTURE"
        )

        score += 2

    elif (
        lower_highs
        and lower_lows
    ):
        patterns.append(
            "DOWNTREND_STRUCTURE"
        )

        score -= 2

    # ---------------------------------
    # VALIDATED REVERSAL PATTERNS
    # ---------------------------------

    lookback = min(
        20,
        len(df),
    )

    window = (
        df.tail(lookback)
        .reset_index(
            drop=True
        )
    )

    double_top = _find_double_top(
        window["high"].astype(float)
    )

    double_bottom = (
        _find_double_bottom(
            window["low"].astype(float)
        )
    )

    selected_reversal, conflict_resolved = (
        _resolve_reversal_conflict(
            double_top=double_top,
            double_bottom=double_bottom,
        )
    )

    if selected_reversal:

        reversal_pattern = (
            selected_reversal[
                "pattern"
            ]
        )

        patterns.append(
            reversal_pattern
        )

        if (
            reversal_pattern
            == "DOUBLE_TOP"
        ):
            score -= 2

        elif (
            reversal_pattern
            == "DOUBLE_BOTTOM"
        ):
            score += 2

    # ---------------------------------
    # CONSOLIDATION
    # ---------------------------------

    recent_window = df.tail(
        min(
            10,
            len(df),
        )
    )

    highest = float(
        recent_window[
            "high"
        ].max()
    )

    lowest = float(
        recent_window[
            "low"
        ].min()
    )

    average_price = float(
        recent_window[
            "close"
        ].mean()
    )

    if average_price != 0:

        range_percent = (
            (
                highest
                - lowest
            )
            / average_price
        )

        if range_percent <= 0.03:
            patterns.append(
                "CONSOLIDATION"
            )

    # ---------------------------------
    # PRICE COMPRESSION
    # ---------------------------------

    candle_ranges = (
        highs - lows
    ).tail(5).tolist()

    if len(candle_ranges) >= 5:

        shrinking_ranges = all(
            candle_ranges[index]
            <= candle_ranges[
                index - 1
            ]
            for index in range(
                1,
                len(candle_ranges),
            )
        )

        if shrinking_ranges:
            patterns.append(
                "PRICE_COMPRESSION"
            )

    # ---------------------------------
    # BREAKOUT / BREAKDOWN
    # ---------------------------------

    if len(df) >= 6:

        previous = df.iloc[
            -6:-1
        ]

        previous_resistance = float(
            previous[
                "high"
            ].max()
        )

        previous_support = float(
            previous[
                "low"
            ].min()
        )

        latest_close = float(
            closes.iloc[-1]
        )

        if (
            latest_close
            > previous_resistance
        ):
            patterns.append(
                "BREAKOUT"
            )

            score += 3

        elif (
            latest_close
            < previous_support
        ):
            patterns.append(
                "BREAKDOWN"
            )

            score -= 3

    # ---------------------------------
    # VOLUME CONFIRMATION
    # ---------------------------------

    volume_confirmation = False

    if len(df) >= 6:

        previous_average_volume = float(
            volumes.iloc[
                -6:-1
            ].mean()
        )

        latest_volume = float(
            volumes.iloc[-1]
        )

        if (
            previous_average_volume > 0
            and latest_volume
            >= previous_average_volume
            * 1.5
        ):
            volume_confirmation = True

            patterns.append(
                "HIGH_VOLUME_CONFIRMATION"
            )

            if "BREAKOUT" in patterns:
                score += 2

            elif (
                "BREAKDOWN"
                in patterns
            ):
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
        "volume_confirmation": (
            volume_confirmation
        ),
        "pattern_conflict_resolved": (
            conflict_resolved
        ),
    }