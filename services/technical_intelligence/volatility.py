"""Completed-candle volatility and volume evidence, without regime output."""
from __future__ import annotations

from .indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_volume_average,
    calculate_vwap,
)


def _blocked(name, timeframe, minimum, available):
    from services.contracts.technical_indicator_value_v1 import (
        TechnicalIndicatorValueV1,
    )

    return TechnicalIndicatorValueV1(
        name,
        timeframe,
        None,
        "NONE",
        "INSUFFICIENT_HISTORY",
        minimum,
        available,
        blockers=("insufficient_complete_candles",),
    )


def _unavailable_volume(name, timeframe, minimum, available):
    from services.contracts.technical_indicator_value_v1 import (
        TechnicalIndicatorValueV1,
    )

    return TechnicalIndicatorValueV1(
        name,
        timeframe,
        None,
        "NONE",
        "UNAVAILABLE",
        minimum,
        available,
        blockers=("volume_evidence_unavailable",),
    )


def evaluate_volatility_intelligence(series, policy=None) -> dict[str, object]:
    from services.contracts import (
        MarketCandleSeriesV1,
        TechnicalIndicatorValueV1,
    )
    from services.contracts.technical_intelligence_policy_v1 import (
        DEFAULT_TECHNICAL_INTELLIGENCE_POLICY,
    )

    if policy is None:
        policy = DEFAULT_TECHNICAL_INTELLIGENCE_POLICY

    if not isinstance(series, MarketCandleSeriesV1):
        raise ValueError("A canonical candle series is required.")

    candles = tuple(
        candle
        for candle in series.candles
        if candle.is_complete
    )
    count = len(candles)

    highs = tuple(candle.high_price for candle in candles)
    lows = tuple(candle.low_price for candle in candles)
    closes = tuple(candle.close_price for candle in candles)
    volumes = tuple(candle.volume for candle in candles)

    atr = calculate_atr(
        highs,
        lows,
        closes,
        policy.atr_period,
    )
    bands = calculate_bollinger_bands(
        closes,
        policy.bollinger_period,
        policy.bollinger_stddev,
    )

    usable_volume = bool(volumes) and any(
        volume > 0
        for volume in volumes
    )

    if usable_volume:
        average = calculate_volume_average(
            volumes,
            policy.volume_lookback,
        )
        vwap = calculate_vwap(
            highs,
            lows,
            closes,
            volumes,
        )
    else:
        average = None
        vwap = None

    atr_indicator = (
        TechnicalIndicatorValueV1(
            "ATR",
            series.timeframe,
            atr,
            (
                "HIGH"
                if atr is not None
                and atr / closes[-1] >= 0.02
                else "LOW"
            ),
            "VALID",
            policy.atr_period,
            count,
            (("period", policy.atr_period),),
        )
        if atr is not None
        else _blocked(
            "ATR",
            series.timeframe,
            policy.atr_period,
            count,
        )
    )

    bollinger_indicator = (
        TechnicalIndicatorValueV1(
            "BOLLINGER_WIDTH",
            series.timeframe,
            (
                (bands[2] - bands[0]) / bands[1]
                if bands[1]
                else 0.0
            ),
            "EXPANDING",
            "VALID",
            policy.bollinger_period,
            count,
            (
                ("period", policy.bollinger_period),
                ("stddev", policy.bollinger_stddev),
            ),
        )
        if bands is not None
        else _blocked(
            "BOLLINGER_WIDTH",
            series.timeframe,
            policy.bollinger_period,
            count,
        )
    )

    if usable_volume:
        volume_average_indicator = (
            TechnicalIndicatorValueV1(
                "VOLUME_AVERAGE",
                series.timeframe,
                average,
                (
                    "HIGH"
                    if average is not None
                    and volumes[-1] >= average
                    else "LOW"
                ),
                "VALID",
                policy.volume_lookback,
                count,
                (("period", policy.volume_lookback),),
            )
            if average is not None
            else _blocked(
                "VOLUME_AVERAGE",
                series.timeframe,
                policy.volume_lookback,
                count,
            )
        )

        vwap_indicator = (
            TechnicalIndicatorValueV1(
                "VWAP",
                series.timeframe,
                vwap,
                (
                    "BULLISH"
                    if vwap is not None
                    and closes[-1] > vwap
                    else "BEARISH"
                ),
                "VALID",
                1,
                count,
            )
            if vwap is not None
            else _unavailable_volume(
                "VWAP",
                series.timeframe,
                1,
                count,
            )
        )
    else:
        volume_average_indicator = _unavailable_volume(
            "VOLUME_AVERAGE",
            series.timeframe,
            policy.volume_lookback,
            count,
        )
        vwap_indicator = _unavailable_volume(
            "VWAP",
            series.timeframe,
            1,
            count,
        )

    values = (
        atr_indicator,
        bollinger_indicator,
        volume_average_indicator,
        vwap_indicator,
    )

    # Price-based volatility requires ATR and Bollinger history.
    # Volume-derived indicators are intentionally independent:
    # unavailable volume must not invalidate otherwise valid
    # price technical evidence.
    if atr is None or bands is None:
        return {
            "category": "VOLATILITY",
            "bias": "UNAVAILABLE",
            "strength": 0.0,
            "indicators": values,
            "blockers": ("insufficient_complete_candles",),
            "warnings": (),
        }

    width = (
        (bands[2] - bands[0]) / bands[1]
        if bands[1]
        else 0.0
    )
    price_volatility_strength = min(
        1.0,
        width + atr / closes[-1],
    )

    if vwap is None:
        bias = "NEUTRAL"
        strength = price_volatility_strength
        warnings = ("volume_evidence_unavailable",)
    else:
        bias = (
            "BULLISH"
            if closes[-1] > vwap
            else "BEARISH"
            if closes[-1] < vwap
            else "NEUTRAL"
        )
        strength = (
            price_volatility_strength
            if bias != "NEUTRAL"
            else 0.0
        )
        warnings = ()

    return {
        "category": "VOLATILITY",
        "bias": bias,
        "strength": strength,
        "indicators": values,
        "blockers": (),
        "warnings": warnings,
    }
