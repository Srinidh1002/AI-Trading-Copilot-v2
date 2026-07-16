"""Context-aware volume intelligence engine.

Analyses OHLCV data for:
- Relative volume
- Volume spikes
- Price/volume divergence
- Volume behaviour near support and resistance
- Breakout and breakdown confirmation

This module provides evidence only.
It does not authorize trades or place orders.
"""

from __future__ import annotations

import math

import pandas as pd


_REQUIRED_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def _finite_float(value):
    """Return a finite float or None."""

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def analyse_volume_intelligence(
    df,
    support=None,
    resistance=None,
    volume_lookback=20,
    divergence_lookback=5,
    spike_threshold=1.5,
    level_proximity_percent=0.25,
):
    """Analyse current volume behaviour in market context.

    Args:
        df: Lowercase OHLCV DataFrame.
        support: Existing market support level.
        resistance: Existing market resistance level.
        volume_lookback: Candles used for average volume.
        divergence_lookback: Candles used for price/volume trend.
        spike_threshold: Relative-volume ratio considered a spike.
        level_proximity_percent: Maximum percentage distance from a
            level to consider price near support or resistance.

    Returns:
        Structured volume evidence. This result does not independently
        authorize a trade.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    missing = _REQUIRED_COLUMNS.difference(df.columns)

    if missing:
        raise ValueError(
            "Missing required OHLCV columns: "
            + ", ".join(sorted(missing))
        )

    if df.empty:
        raise ValueError("No OHLCV data provided.")

    if volume_lookback < 2:
        raise ValueError(
            "volume_lookback must be at least 2."
        )

    if divergence_lookback < 2:
        raise ValueError(
            "divergence_lookback must be at least 2."
        )

    if spike_threshold <= 0:
        raise ValueError(
            "spike_threshold must be greater than zero."
        )

    if level_proximity_percent < 0:
        raise ValueError(
            "level_proximity_percent cannot be negative."
        )

    data = df.copy()

    for column in _REQUIRED_COLUMNS:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=list(_REQUIRED_COLUMNS)
    )

    if data.empty:
        raise ValueError(
            "No valid OHLCV rows are available."
        )

    latest = data.iloc[-1]

    latest_close = _finite_float(
        latest["close"]
    )

    latest_volume = _finite_float(
        latest["volume"]
    )

    if (
        latest_close is None
        or latest_close <= 0
    ):
        raise ValueError(
            "Latest close must be greater than zero."
        )

    if (
        latest_volume is None
        or latest_volume < 0
    ):
        raise ValueError(
            "Latest volume cannot be negative."
        )

    # ---------------------------------
    # RELATIVE VOLUME
    # Use previous candles as baseline,
    # excluding the current candle.
    # ---------------------------------

    historical_volume = (
        data["volume"]
        .iloc[:-1]
        .tail(volume_lookback)
    )

    average_volume = None
    relative_volume = None
    volume_spike = False

    if not historical_volume.empty:

        average_volume = _finite_float(
            historical_volume.mean()
        )

        if (
            average_volume is not None
            and average_volume > 0
        ):
            relative_volume = (
                latest_volume
                / average_volume
            )

            volume_spike = (
                relative_volume
                >= spike_threshold
            )

        elif average_volume == 0:
            # Index feeds can legitimately contain an all-zero volume series.
            # Keep the report numeric whenever historical candles exist while
            # preserving the existing non-spike behaviour.
            relative_volume = 0.0

    # ---------------------------------
    # PRICE / VOLUME TREND
    # ---------------------------------

    divergence_data = data.tail(
        divergence_lookback
    )

    price_change_percent = None
    volume_change_percent = None

    price_trend = "UNKNOWN"
    volume_trend = "UNKNOWN"
    divergence = "NONE"

    if len(divergence_data) >= 2:

        first_close = _finite_float(
            divergence_data["close"].iloc[0]
        )

        first_volume = _finite_float(
            divergence_data["volume"].iloc[0]
        )

        if (
            first_close is not None
            and first_close > 0
        ):
            price_change_percent = (
                (
                    latest_close
                    - first_close
                )
                / first_close
                * 100
            )

            if price_change_percent > 0:
                price_trend = "RISING"

            elif price_change_percent < 0:
                price_trend = "FALLING"

            else:
                price_trend = "FLAT"

        if (
            first_volume is not None
            and first_volume > 0
        ):
            volume_change_percent = (
                (
                    latest_volume
                    - first_volume
                )
                / first_volume
                * 100
            )

            if volume_change_percent > 0:
                volume_trend = "RISING"

            elif volume_change_percent < 0:
                volume_trend = "FALLING"

            else:
                volume_trend = "FLAT"

    # ---------------------------------
    # DIVERGENCE
    # ---------------------------------

    if (
        price_trend == "RISING"
        and volume_trend == "FALLING"
    ):
        divergence = "BEARISH_WARNING"

    elif (
        price_trend == "FALLING"
        and volume_trend == "FALLING"
    ):
        divergence = "SELLING_PRESSURE_FADING"

    # ---------------------------------
    # SUPPORT / RESISTANCE CONTEXT
    # ---------------------------------

    support = _finite_float(support)
    resistance = _finite_float(resistance)

    near_support = False
    near_resistance = False

    if (
        support is not None
        and support > 0
    ):
        support_distance_percent = (
            abs(
                latest_close
                - support
            )
            / support
            * 100
        )

        near_support = (
            support_distance_percent
            <= level_proximity_percent
        )

    if (
        resistance is not None
        and resistance > 0
    ):
        resistance_distance_percent = (
            abs(
                latest_close
                - resistance
            )
            / resistance
            * 100
        )

        near_resistance = (
            resistance_distance_percent
            <= level_proximity_percent
        )

    # ---------------------------------
    # CONTEXTUAL SIGNALS
    # ---------------------------------

    signals = []
    bullish_evidence = []
    bearish_evidence = []
    warnings = []

    if volume_spike:
        signals.append("VOLUME_SPIKE")

    if divergence == "BEARISH_WARNING":
        warnings.append(
            "Price is rising while volume is falling."
        )
        bearish_evidence.append(
            "Rising price lacks increasing volume participation."
        )

    elif divergence == "SELLING_PRESSURE_FADING":
        bullish_evidence.append(
            "Price is falling while volume is falling, "
            "indicating reduced selling participation."
        )

    if (
        near_support
        and volume_spike
    ):
        signals.append(
            "HIGH_VOLUME_AT_SUPPORT"
        )

        bullish_evidence.append(
            "A volume spike occurred near support."
        )

    if (
        near_resistance
        and volume_spike
    ):
        signals.append(
            "HIGH_VOLUME_AT_RESISTANCE"
        )

        warnings.append(
            "A volume spike occurred near resistance; "
            "confirm whether price breaks out or rejects."
        )

    # ---------------------------------
    # BREAKOUT / BREAKDOWN CONFIRMATION
    # ---------------------------------

    breakout_confirmed = bool(
        resistance is not None
        and latest_close > resistance
        and volume_spike
    )

    breakdown_confirmed = bool(
        support is not None
        and latest_close < support
        and volume_spike
    )

    if breakout_confirmed:
        signals.append(
            "VOLUME_CONFIRMED_BREAKOUT"
        )

        bullish_evidence.append(
            "Price broke resistance with elevated volume."
        )

    if breakdown_confirmed:
        signals.append(
            "VOLUME_CONFIRMED_BREAKDOWN"
        )

        bearish_evidence.append(
            "Price broke support with elevated volume."
        )

    # ---------------------------------
    # DIRECTIONAL INTERPRETATION
    # Evidence only, not a trade order.
    # ---------------------------------

    bullish_score = len(
        bullish_evidence
    )

    bearish_score = len(
        bearish_evidence
    )

    if bullish_score > bearish_score:
        bias = "BULLISH"

    elif bearish_score > bullish_score:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "relative_volume": (
            round(relative_volume, 2)
            if relative_volume is not None
            else None
        ),
        "latest_volume": latest_volume,
        "average_volume": (
            round(average_volume, 2)
            if average_volume is not None
            else None
        ),
        "volume_spike": volume_spike,
        "price_trend": price_trend,
        "volume_trend": volume_trend,
        "price_change_percent": (
            round(price_change_percent, 2)
            if price_change_percent is not None
            else None
        ),
        "volume_change_percent": (
            round(volume_change_percent, 2)
            if volume_change_percent is not None
            else None
        ),
        "divergence": divergence,
        "near_support": near_support,
        "near_resistance": near_resistance,
        "breakout_confirmed": breakout_confirmed,
        "breakdown_confirmed": breakdown_confirmed,
        "signals": signals,
        "bullish_evidence": bullish_evidence,
        "bearish_evidence": bearish_evidence,
        "warnings": warnings,
    }
