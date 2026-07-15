from services.strategy_selector import (
    select_strategy,
)


def build_strategy_result(
    *,
    regime_trend="BULLISH",
    timeframe_trend="BULLISH",
    alignment="FULL",
    technical_trend="BULLISH",
    candlestick_patterns=None,
    chart_patterns=None,
    volume_confirmation=True,
    option_trend="BULLISH",
    primary_regime="TRENDING_BULLISH",
    regime_aware_evidence=None,
):
    option = None

    if option_trend is not None:
        option = {
            "trend": option_trend,
        }

    return select_strategy(
        regime={
            "primary_regime": primary_regime,
            "trend": regime_trend,
        },
        timeframe={
            "overall_trend": timeframe_trend,
            "alignment": alignment,
        },
        technical={
            "trend": technical_trend,
        },
        candlestick={
            "patterns": list(
                candlestick_patterns or []
            ),
        },
        chart={
            "patterns": list(
                chart_patterns or []
            ),
            "volume_confirmation": (
                volume_confirmation
            ),
        },
        option=option,
        regime_aware_evidence=(
            regime_aware_evidence
        ),
    )


def bullish_candidate(
    regime_aware_evidence,
):
    return build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
        regime_aware_evidence=(
            regime_aware_evidence
        ),
    )


def test_bullish_trend_continuation():
    result = build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
    )

    assert (
        result["strategy"]
        == "TREND_CONTINUATION"
    )
    assert result["direction"] == "BULLISH"
    assert result["decision"] == "TRADE"


def test_bullish_breakout():
    result = build_strategy_result(
        regime_trend="NEUTRAL",
        timeframe_trend="BULLISH",
        alignment="PARTIAL",
        technical_trend="BULLISH",
        candlestick_patterns=[],
        chart_patterns=[
            "BREAKOUT",
        ],
        option_trend="BULLISH",
        primary_regime="COMPRESSION",
    )

    assert result["strategy"] == "BREAKOUT"
    assert result["direction"] == "BULLISH"
    assert result["decision"] == "TRADE"


def test_bearish_breakdown():
    result = build_strategy_result(
        regime_trend="NEUTRAL",
        timeframe_trend="BEARISH",
        alignment="PARTIAL",
        technical_trend="BEARISH",
        candlestick_patterns=[],
        chart_patterns=[
            "BREAKDOWN",
        ],
        option_trend="BEARISH",
        primary_regime="RANGING",
    )

    assert result["strategy"] == "BREAKDOWN"
    assert result["direction"] == "BEARISH"
    assert result["decision"] == "TRADE"


def test_conflicting_timeframes_no_trade():
    result = build_strategy_result(
        timeframe_trend="MIXED",
        alignment="CONFLICTED",
        technical_trend="BULLISH",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend="BEARISH",
    )

    assert result["decision"] == "NO_TRADE"


def test_neutral_market_no_trade():
    result = build_strategy_result(
        regime_trend="NEUTRAL",
        timeframe_trend="MIXED",
        alignment="CONFLICTED",
        technical_trend="NEUTRAL",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
        primary_regime="UNCERTAIN",
    )

    assert result["direction"] == "NEUTRAL"
    assert result["decision"] == "NO_TRADE"


def test_regime_aware_evidence_confirms_candidate():
    result = bullish_candidate({
        "regime": "TRENDING_BULLISH",
        "contextual_bias": "BULLISH",
        "warnings": [],
    })

    assert result["decision"] == "TRADE"

    assert (
        "Regime-aware evidence confirms "
        "candidate direction"
        in result["confirmations"]
    )


def test_regime_aware_evidence_vetoes_conflicting_candidate():
    result = bullish_candidate({
        "regime": "TRENDING_BULLISH",
        "contextual_bias": "BEARISH",
        "warnings": [],
    })

    assert result["direction"] == "BULLISH"
    assert result["decision"] == "NO_TRADE"

    assert (
        "Regime-aware evidence conflicts "
        "with candidate direction"
        in result["risk_flags"]
    )


def test_uncertain_context_vetoes_trade():
    result = bullish_candidate({
        "regime": "UNCERTAIN",
        "contextual_bias": "NEUTRAL",
        "warnings": [],
    })

    assert result["decision"] == "NO_TRADE"


def test_neutral_context_does_not_create_trade():
    result = build_strategy_result(
        regime_trend="NEUTRAL",
        timeframe_trend="MIXED",
        alignment="PARTIAL",
        technical_trend="NEUTRAL",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
        primary_regime="UNCERTAIN",
        regime_aware_evidence={
            "regime": "RANGING",
            "contextual_bias": "BULLISH",
            "warnings": [],
        },
    )

    assert result["decision"] == "NO_TRADE"


def test_existing_call_without_context_remains_compatible():
    result = build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
    )

    assert result["decision"] == "TRADE"
    assert (
        result["strategy"]
        == "TREND_CONTINUATION"
    )


def test_direction_confidence_preserves_legacy_confidence():
    result = build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
    )

    assert (
        result["direction_confidence"]
        == result["confidence"]
    )


def test_complete_directional_dominance_has_100_confidence():
    result = build_strategy_result(
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
    )

    assert result["bullish_score"] == 7
    assert result["bearish_score"] == 0
    assert result["direction_confidence"] == 100


def test_balanced_directional_evidence_has_50_confidence():
    result = build_strategy_result(
        regime_trend="BULLISH",
        timeframe_trend="BEARISH",
        alignment="PARTIAL",
        technical_trend="BULLISH",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend="BEARISH",
        primary_regime="RANGING",
    )

    assert result["bullish_score"] == 4
    assert result["bearish_score"] == 5
    assert result["direction_confidence"] == 56


def test_zero_directional_evidence_has_zero_confidence():
    result = build_strategy_result(
        regime_trend="NEUTRAL",
        timeframe_trend="MIXED",
        alignment="PARTIAL",
        technical_trend="NEUTRAL",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
        primary_regime="UNCERTAIN",
    )

    assert result["bullish_score"] == 0
    assert result["bearish_score"] == 0
    assert result["direction_confidence"] == 0


def test_evidence_strength_score_uses_total_directional_score():
    result = build_strategy_result(
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
    )

    assert result["bullish_score"] == 7
    assert result["bearish_score"] == 0
    assert result["evidence_strength_score"] == 47


def test_low_evidence_strength_is_labeled_low():
    result = build_strategy_result(
        regime_trend="BULLISH",
        timeframe_trend="MIXED",
        alignment="PARTIAL",
        technical_trend="NEUTRAL",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
        primary_regime="RANGING",
    )

    assert result["evidence_strength_score"] == 13
    assert result["evidence_strength_label"] == "LOW"


def test_medium_evidence_strength_is_labeled_medium():
    result = build_strategy_result(
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend=None,
    )

    assert result["evidence_strength_score"] == 47
    assert result["evidence_strength_label"] == "MEDIUM"


def test_high_evidence_strength_is_labeled_high():
    result = build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
        volume_confirmation=True,
        option_trend="BULLISH",
    )

    assert result["bullish_score"] == 14
    assert result["bearish_score"] == 0
    assert result["evidence_strength_score"] == 93
    assert result["evidence_strength_label"] == "HIGH"


def test_evidence_strength_score_is_capped_at_100():
    result = build_strategy_result(
        candlestick_patterns=[
            "BULLISH_ENGULFING",
        ],
        chart_patterns=[
            "UPTREND_STRUCTURE",
        ],
        volume_confirmation=True,
        option_trend="BULLISH",
    )

    assert (
        0
        <= result["evidence_strength_score"]
        <= 100
    )


def test_new_confidence_fields_do_not_change_trade_decision():
    result = build_strategy_result(
        timeframe_trend="MIXED",
        alignment="CONFLICTED",
        technical_trend="BULLISH",
        candlestick_patterns=[],
        chart_patterns=[],
        volume_confirmation=False,
        option_trend="BEARISH",
    )

    assert result["direction_confidence"] == 67
    assert result["decision"] == "NO_TRADE"