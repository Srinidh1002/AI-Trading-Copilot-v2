"""
Strategy selection engine.

Combines independent market signals and selects the most suitable
strategy without forcing a trade.
"""

from services.strategy_library import (
    get_strategies_for_regime,
)


BULLISH_PATTERNS = {
    "BULLISH_ENGULFING",
    "HAMMER",
    "BULLISH_BREAKOUT",
    "BREAKOUT",
    "DOUBLE_BOTTOM",
    "UPTREND_STRUCTURE",
}

BEARISH_PATTERNS = {
    "BEARISH_ENGULFING",
    "SHOOTING_STAR",
    "BEARISH_BREAKDOWN",
    "BREAKDOWN",
    "DOUBLE_TOP",
    "DOWNTREND_STRUCTURE",
}


def select_strategy(
    regime,
    timeframe,
    technical,
    candlestick,
    chart,
    option=None,
    regime_aware_evidence=None,
):
    """
    Select the best strategy from multiple independent signals.

    Returns an explainable TRADE or NO_TRADE decision.
    """

    primary_regime = regime.get(
        "primary_regime",
        "UNCERTAIN",
    ).upper()

    suitable_strategies = (
        get_strategies_for_regime(
            primary_regime
        )
    )

    bullish_score = 0
    bearish_score = 0

    confirmations = []
    risk_flags = []

    # ---------------------------------
    # MARKET REGIME
    # ---------------------------------

    market_trend = regime.get(
        "trend",
        "NEUTRAL",
    ).upper()

    if market_trend == "BULLISH":
        bullish_score += 2
        confirmations.append(
            "Bullish market regime"
        )

    elif market_trend == "BEARISH":
        bearish_score += 2
        confirmations.append(
            "Bearish market regime"
        )

    # ---------------------------------
    # MULTI-TIMEFRAME ANALYSIS
    # ---------------------------------

    timeframe_trend = timeframe.get(
        "overall_trend",
        "MIXED",
    ).upper()

    alignment = timeframe.get(
        "alignment",
        "CONFLICTED",
    ).upper()

    if timeframe_trend == "BULLISH":
        bullish_score += 3
        confirmations.append(
            "Bullish multi-timeframe trend"
        )

    elif timeframe_trend == "BEARISH":
        bearish_score += 3
        confirmations.append(
            "Bearish multi-timeframe trend"
        )

    if alignment == "FULL":
        confirmations.append(
            "Full timeframe alignment"
        )

    elif alignment == "CONFLICTED":
        risk_flags.append(
            "Conflicting timeframe signals"
        )

    # ---------------------------------
    # TECHNICAL ANALYSIS
    # ---------------------------------

    technical_trend = technical.get(
        "trend",
        "NEUTRAL",
    ).upper()

    if technical_trend == "BULLISH":
        bullish_score += 2
        confirmations.append(
            "Technical analysis bullish"
        )

    elif technical_trend == "BEARISH":
        bearish_score += 2
        confirmations.append(
            "Technical analysis bearish"
        )

    # ---------------------------------
    # CANDLESTICK PATTERNS
    # ---------------------------------

    candlestick_patterns = set(
        candlestick.get(
            "patterns",
            [],
        )
    )

    bullish_candles = (
        candlestick_patterns
        & BULLISH_PATTERNS
    )

    bearish_candles = (
        candlestick_patterns
        & BEARISH_PATTERNS
    )

    if bullish_candles:
        bullish_score += 2
        confirmations.append(
            "Bullish candlestick confirmation"
        )

    if bearish_candles:
        bearish_score += 2
        confirmations.append(
            "Bearish candlestick confirmation"
        )

    if bullish_candles and bearish_candles:
        risk_flags.append(
            "Conflicting bullish and bearish candlestick patterns"
        )

    # ---------------------------------
    # CHART PATTERNS
    # ---------------------------------

    chart_patterns = set(
        chart.get(
            "patterns",
            [],
        )
    )

    bullish_chart = (
        chart_patterns
        & BULLISH_PATTERNS
    )

    bearish_chart = (
        chart_patterns
        & BEARISH_PATTERNS
    )

    if bullish_chart:
        bullish_score += 3
        confirmations.append(
            "Bullish chart-pattern confirmation"
        )

    if bearish_chart:
        bearish_score += 3
        confirmations.append(
            "Bearish chart-pattern confirmation"
        )

    # Important:
    # Do not trust a setup when chart patterns
    # simultaneously indicate both directions.
    if bullish_chart and bearish_chart:
        risk_flags.append(
            "Conflicting bullish and bearish chart patterns"
        )

    volume_confirmation = bool(
        chart.get(
            "volume_confirmation",
            False,
        )
    )

    if volume_confirmation:
        confirmations.append(
            "Volume confirmation present"
        )

    # ---------------------------------
    # OPTIONS SENTIMENT
    # ---------------------------------

    if option:
        option_trend = option.get(
            "trend",
            option.get(
                "signal",
                "NEUTRAL",
            ),
        ).upper()

        if option_trend == "BULLISH":
            bullish_score += 2
            confirmations.append(
                "Options sentiment bullish"
            )

        elif option_trend == "BEARISH":
            bearish_score += 2
            confirmations.append(
                "Options sentiment bearish"
            )

    # ---------------------------------
    # CONFLICT DETECTION
    # ---------------------------------

    total_directional_score = (
        bullish_score
        + bearish_score
    )

    score_difference = abs(
        bullish_score
        - bearish_score
    )

    if (
        bullish_score > 0
        and bearish_score > 0
        and score_difference <= 2
    ):
        risk_flags.append(
            "Bullish and bearish evidence is closely balanced"
        )

    # ---------------------------------
    # DIRECTION
    # ---------------------------------

    if bullish_score > bearish_score:
        direction = "BULLISH"

    elif bearish_score > bullish_score:
        direction = "BEARISH"

    else:
        direction = "NEUTRAL"

    # ---------------------------------
    # DIRECTION CONFIDENCE
    # ---------------------------------

    if total_directional_score == 0:
        direction_confidence = 0

    else:
        direction_confidence = round(
            (
                max(
                    bullish_score,
                    bearish_score,
                )
                / total_directional_score
            )
            * 100
        )

    # Preserve the legacy confidence field
    # for backward compatibility.
    confidence = direction_confidence

    # ---------------------------------
    # EVIDENCE STRENGTH
    # ---------------------------------

    maximum_directional_score = 15

    evidence_strength_score = round(
        min(
            total_directional_score
            / maximum_directional_score,
            1.0,
        )
        * 100
    )

    if evidence_strength_score >= 70:
        evidence_strength_label = "HIGH"

    elif evidence_strength_score >= 35:
        evidence_strength_label = "MEDIUM"

    else:
        evidence_strength_label = "LOW"

    # ---------------------------------
    # BREAKOUT CONFIRMATION
    # ---------------------------------

    bullish_breakout_confirmed = (
        "BREAKOUT" in chart_patterns
        or "BULLISH_BREAKOUT"
        in candlestick_patterns
    )

    bearish_breakdown_confirmed = (
        "BREAKDOWN" in chart_patterns
        or "BEARISH_BREAKDOWN"
        in candlestick_patterns
    )

    # ---------------------------------
    # SELECT STRATEGY
    # ---------------------------------

    selected_strategy = "NO_TRADE"

    if direction == "BULLISH":

        if (
            "BREAKOUT" in chart_patterns
            and "BREAKOUT"
            in suitable_strategies
        ):
            selected_strategy = "BREAKOUT"

        elif (
            "VOLATILITY_EXPANSION"
            in suitable_strategies
            and primary_regime
            in {
                "COMPRESSION",
                "LOW_VOLATILITY",
            }
            and bullish_breakout_confirmed
        ):
            selected_strategy = (
                "VOLATILITY_EXPANSION"
            )

        elif (
            "TREND_CONTINUATION"
            in suitable_strategies
        ):
            selected_strategy = (
                "TREND_CONTINUATION"
            )

        elif (
            "MOMENTUM"
            in suitable_strategies
        ):
            selected_strategy = "MOMENTUM"

        elif (
            "MEAN_REVERSION"
            in suitable_strategies
        ):
            selected_strategy = (
                "MEAN_REVERSION"
            )

    elif direction == "BEARISH":

        if (
            "BREAKDOWN" in chart_patterns
            and "BREAKDOWN"
            in suitable_strategies
        ):
            selected_strategy = "BREAKDOWN"

        elif (
            "VOLATILITY_EXPANSION"
            in suitable_strategies
            and primary_regime
            in {
                "COMPRESSION",
                "LOW_VOLATILITY",
            }
            and bearish_breakdown_confirmed
        ):
            selected_strategy = (
                "VOLATILITY_EXPANSION"
            )

        elif (
            "TREND_CONTINUATION"
            in suitable_strategies
        ):
            selected_strategy = (
                "TREND_CONTINUATION"
            )

        elif (
            "MOMENTUM"
            in suitable_strategies
        ):
            selected_strategy = "MOMENTUM"

        elif (
            "MEAN_REVERSION"
            in suitable_strategies
        ):
            selected_strategy = (
                "MEAN_REVERSION"
            )
    # ---------------------------------
    # REGIME-AWARE EVIDENCE GATE
    #
    # This layer does not add directional
    # score and cannot create a trade.
    # It can only validate, warn, or veto
    # an already existing candidate.
    # ---------------------------------

    contextual_bias = "NEUTRAL"
    contextual_regime = primary_regime

    if regime_aware_evidence is not None:

        contextual_bias = str(
            regime_aware_evidence.get(
                "contextual_bias",
                "NEUTRAL",
            )
        ).upper()

        contextual_regime = str(
            regime_aware_evidence.get(
                "regime",
                primary_regime,
            )
        ).upper()

        evidence_warnings = (
            regime_aware_evidence.get(
                "warnings",
                [],
            )
            or []
        )

        for warning in evidence_warnings:
            warning_text = str(
                warning
            ).strip()

            if (
                warning_text
                and warning_text
                not in risk_flags
            ):
                risk_flags.append(
                    warning_text
                )

        if (
            direction
            in {
                "BULLISH",
                "BEARISH",
            }
            and contextual_bias
            in {
                "BULLISH",
                "BEARISH",
            }
            and contextual_bias
            != direction
        ):
            risk_flags.append(
                "Regime-aware evidence conflicts "
                "with candidate direction"
            )

        elif (
            direction
            in {
                "BULLISH",
                "BEARISH",
            }
            and contextual_bias
            == direction
        ):
            confirmations.append(
                "Regime-aware evidence confirms "
                "candidate direction"
            )

        if contextual_regime == "UNCERTAIN":
            risk_flags.append(
                "Regime-aware evidence identifies "
                "an uncertain market"
            )
    # ---------------------------------
    # TRADE / NO TRADE
    # ---------------------------------

    blocking_risks = {
        "Conflicting timeframe signals",
        "Conflicting bullish and bearish chart patterns",
        "Conflicting bullish and bearish candlestick patterns",
        (
            "Regime-aware evidence conflicts "
            "with candidate direction"
        ),
        (
            "Regime-aware evidence identifies "
            "an uncertain market"
        ),
    }
    has_blocking_risk = any(
        risk in blocking_risks
        for risk in risk_flags
    )

    if (
        selected_strategy == "NO_TRADE"
        or direction == "NEUTRAL"
        or confidence < 65
        or has_blocking_risk
    ):
        decision = "NO_TRADE"

    else:
        decision = "TRADE"

    return {
        "strategy": selected_strategy,
        "direction": direction,
        "confidence": confidence,
        "direction_confidence": (
            direction_confidence
        ),
        "evidence_strength_score": (
            evidence_strength_score
        ),
        "evidence_strength_label": (
            evidence_strength_label
        ),
        "decision": decision,
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "confirmations": confirmations,
        "risk_flags": risk_flags,
        "suitable_strategies": suitable_strategies,
        "contextual_bias": contextual_bias,
        "contextual_regime": contextual_regime,
    }