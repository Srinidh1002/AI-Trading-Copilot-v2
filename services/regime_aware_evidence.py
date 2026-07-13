"""Regime-aware market evidence router.

Selects which analytical evidence is most relevant to the
current market regime.

This module does not place orders and does not independently
authorize trades.
"""

from __future__ import annotations


VALID_REGIMES = {
    "TRENDING_BULLISH",
    "TRENDING_BEARISH",
    "RANGING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "COMPRESSION",
    "UNCERTAIN",
}


def evaluate_regime_aware_evidence(
    regime,
    timeframe,
    technical,
    candlestick,
    chart,
    volume,
):
    """Select and interpret evidence according to market regime."""

    primary_regime = str(
        regime.get(
            "primary_regime",
            "UNCERTAIN",
        )
    ).upper()

    if primary_regime not in VALID_REGIMES:
        primary_regime = "UNCERTAIN"

    bullish_evidence = []
    bearish_evidence = []
    confirmations = []
    warnings = []
    relevant_signals = []

    timeframe_trend = str(
        timeframe.get(
            "overall_trend",
            "MIXED",
        )
    ).upper()

    technical_trend = str(
        technical.get(
            "trend",
            "SIDEWAYS",
        )
    ).upper()

    volume_bias = str(
        volume.get(
            "bias",
            "NEUTRAL",
        )
    ).upper()

    volume_signals = set(
        volume.get(
            "signals",
            [],
        )
    )

    divergence = str(
        volume.get(
            "divergence",
            "NONE",
        )
    ).upper()

    # ---------------------------------
    # TRENDING MARKET
    # ---------------------------------

    if primary_regime in {
        "TRENDING_BULLISH",
        "TRENDING_BEARISH",
    }:
        relevant_signals.extend([
            "MULTI_TIMEFRAME_TREND",
            "TECHNICAL_TREND",
            "VOLUME_PARTICIPATION",
            "BREAKOUT_CONFIRMATION",
            "DIVERGENCE_WARNING",
        ])

        if timeframe_trend == "BULLISH":
            bullish_evidence.append(
                "Multi-timeframe trend is bullish."
            )

        elif timeframe_trend == "BEARISH":
            bearish_evidence.append(
                "Multi-timeframe trend is bearish."
            )

        if technical_trend == "BULLISH":
            bullish_evidence.append(
                "Technical trend supports bullish continuation."
            )

        elif technical_trend == "BEARISH":
            bearish_evidence.append(
                "Technical trend supports bearish continuation."
            )

        if (
            "VOLUME_CONFIRMED_BREAKOUT"
            in volume_signals
        ):
            bullish_evidence.append(
                "Breakout is confirmed by elevated volume."
            )

        if (
            "VOLUME_CONFIRMED_BREAKDOWN"
            in volume_signals
        ):
            bearish_evidence.append(
                "Breakdown is confirmed by elevated volume."
            )

        if divergence == "BEARISH_WARNING":
            warnings.append(
                "Rising price has weakening volume participation."
            )

        if (
            divergence
            == "SELLING_PRESSURE_FADING"
        ):
            warnings.append(
                "Bearish continuation may be weakening as "
                "selling participation falls."
            )

    # ---------------------------------
    # RANGING MARKET
    # ---------------------------------

    elif primary_regime == "RANGING":
        relevant_signals.extend([
            "SUPPORT_RESISTANCE",
            "VOLUME_AT_LEVELS",
            "BREAKOUT_CONFIRMATION",
            "MEAN_REVERSION_CONTEXT",
        ])

        if (
            "HIGH_VOLUME_AT_SUPPORT"
            in volume_signals
        ):
            bullish_evidence.append(
                "Elevated volume is present near support."
            )

        if (
            "HIGH_VOLUME_AT_RESISTANCE"
            in volume_signals
        ):
            warnings.append(
                "Elevated volume is present near resistance; "
                "wait for breakout or rejection confirmation."
            )

        if (
            "VOLUME_CONFIRMED_BREAKOUT"
            in volume_signals
        ):
            bullish_evidence.append(
                "Range resistance broke with elevated volume."
            )

        if (
            "VOLUME_CONFIRMED_BREAKDOWN"
            in volume_signals
        ):
            bearish_evidence.append(
                "Range support broke with elevated volume."
            )

    # ---------------------------------
    # COMPRESSION / LOW VOLATILITY
    # ---------------------------------

    elif primary_regime in {
        "COMPRESSION",
        "LOW_VOLATILITY",
    }:
        relevant_signals.extend([
            "VOLUME_EXPANSION",
            "BREAKOUT_CONFIRMATION",
            "BREAKDOWN_CONFIRMATION",
        ])

        if (
            "VOLUME_CONFIRMED_BREAKOUT"
            in volume_signals
        ):
            bullish_evidence.append(
                "Compression expanded upward with volume."
            )

        elif (
            "VOLUME_CONFIRMED_BREAKDOWN"
            in volume_signals
        ):
            bearish_evidence.append(
                "Compression expanded downward with volume."
            )

        elif volume.get(
            "volume_spike",
            False,
        ):
            confirmations.append(
                "Volume expansion is present but direction "
                "still requires price confirmation."
            )

        else:
            warnings.append(
                "No meaningful volume expansion confirms "
                "a volatility breakout."
            )

    # ---------------------------------
    # HIGH VOLATILITY
    # ---------------------------------

    elif primary_regime == "HIGH_VOLATILITY":
        relevant_signals.extend([
            "STRONG_DIRECTIONAL_CONFIRMATION",
            "VOLUME_CONFIRMATION",
            "CONFLICT_CONTROL",
        ])

        if (
            "VOLUME_CONFIRMED_BREAKOUT"
            in volume_signals
        ):
            bullish_evidence.append(
                "High-volatility breakout has volume confirmation."
            )

        if (
            "VOLUME_CONFIRMED_BREAKDOWN"
            in volume_signals
        ):
            bearish_evidence.append(
                "High-volatility breakdown has volume confirmation."
            )

        if volume_bias == "NEUTRAL":
            warnings.append(
                "High volatility lacks clear volume direction."
            )

    # ---------------------------------
    # UNCERTAIN
    # ---------------------------------

    else:
        relevant_signals.append(
            "RISK_CONTROL"
        )

        warnings.append(
            "Market regime is uncertain; directional evidence "
            "should not be trusted aggressively."
        )

    # ---------------------------------
    # VOLUME DIRECTIONAL CONFLICT
    # ---------------------------------

    if (
        volume_bias == "BULLISH"
        and bearish_evidence
    ):
        warnings.append(
            "Volume bias conflicts with bearish contextual evidence."
        )

    elif (
        volume_bias == "BEARISH"
        and bullish_evidence
    ):
        warnings.append(
            "Volume bias conflicts with bullish contextual evidence."
        )

    # ---------------------------------
    # CONTEXTUAL BIAS
    # ---------------------------------

    bullish_count = len(
        bullish_evidence
    )

    bearish_count = len(
        bearish_evidence
    )

    if bullish_count > bearish_count:
        contextual_bias = "BULLISH"

    elif bearish_count > bullish_count:
        contextual_bias = "BEARISH"

    else:
        contextual_bias = "NEUTRAL"

    return {
        "regime": primary_regime,
        "contextual_bias": contextual_bias,
        "bullish_evidence": bullish_evidence,
        "bearish_evidence": bearish_evidence,
        "confirmations": confirmations,
        "warnings": warnings,
        "relevant_signals": relevant_signals,
    }