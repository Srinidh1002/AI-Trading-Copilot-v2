from services.regime_aware_evidence import (
    evaluate_regime_aware_evidence,
)


def evaluate(
    regime_name,
    *,
    timeframe_trend="MIXED",
    technical_trend="SIDEWAYS",
    volume_bias="NEUTRAL",
    volume_signals=None,
    divergence="NONE",
    volume_spike=False,
):
    return evaluate_regime_aware_evidence(
        regime={
            "primary_regime": regime_name,
        },
        timeframe={
            "overall_trend": timeframe_trend,
        },
        technical={
            "trend": technical_trend,
        },
        candlestick={},
        chart={},
        volume={
            "bias": volume_bias,
            "signals": volume_signals or [],
            "divergence": divergence,
            "volume_spike": volume_spike,
        },
    )


def test_trending_market_uses_trend_evidence():

    result = evaluate(
        "TRENDING_BULLISH",
        timeframe_trend="BULLISH",
        technical_trend="BULLISH",
    )

    assert result["contextual_bias"] == "BULLISH"

    assert (
        "MULTI_TIMEFRAME_TREND"
        in result["relevant_signals"]
    )


def test_trending_market_detects_volume_divergence_warning():

    result = evaluate(
        "TRENDING_BULLISH",
        timeframe_trend="BULLISH",
        technical_trend="BULLISH",
        divergence="BEARISH_WARNING",
    )

    assert result["warnings"]


def test_ranging_market_prioritizes_volume_at_support():

    result = evaluate(
        "RANGING",
        volume_signals=[
            "HIGH_VOLUME_AT_SUPPORT",
        ],
    )

    assert result["contextual_bias"] == "BULLISH"

    assert (
        "VOLUME_AT_LEVELS"
        in result["relevant_signals"]
    )


def test_ranging_market_detects_volume_confirmed_breakdown():

    result = evaluate(
        "RANGING",
        volume_signals=[
            "VOLUME_CONFIRMED_BREAKDOWN",
        ],
    )

    assert result["contextual_bias"] == "BEARISH"


def test_compression_requires_volume_expansion():

    result = evaluate(
        "COMPRESSION",
    )

    assert result["contextual_bias"] == "NEUTRAL"

    assert result["warnings"]


def test_compression_accepts_volume_confirmed_breakout():

    result = evaluate(
        "COMPRESSION",
        volume_signals=[
            "VOLUME_CONFIRMED_BREAKOUT",
        ],
    )

    assert result["contextual_bias"] == "BULLISH"


def test_high_volatility_without_volume_direction_warns():

    result = evaluate(
        "HIGH_VOLATILITY",
        volume_bias="NEUTRAL",
    )

    assert result["warnings"]


def test_uncertain_regime_is_conservative():

    result = evaluate(
        "UNCERTAIN",
    )

    assert result["contextual_bias"] == "NEUTRAL"

    assert (
        "RISK_CONTROL"
        in result["relevant_signals"]
    )


def test_unknown_regime_becomes_uncertain():

    result = evaluate(
        "UNKNOWN_REGIME",
    )

    assert result["regime"] == "UNCERTAIN"
    assert result["contextual_bias"] == "NEUTRAL"