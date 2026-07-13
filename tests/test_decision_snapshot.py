from copy import deepcopy

import pytest

from services.decision_snapshot import (
    build_decision_snapshot,
)


def full_pipeline_result():
    return {
        "decision": "TRADE_ALLOWED",
        "market_decision": "TRADE",
        "direction": "BULLISH",
        "market_analysis": {
            "strategy": {
                "strategy": "TREND_CONTINUATION",
                "decision": "TRADE",
                "confidence": 88,
                "risk_flags": [],
            },
            "regime": {
                "primary_regime": "TRENDING_BULLISH",
                "trend": "BULLISH",
                "confidence": 80,
            },
            "timeframe": {
                "overall_trend": "BULLISH",
                "alignment": "FULL",
                "confidence": 90,
            },
            "technical": {
                "trend": "BULLISH",
                "score": 82,
                "confidence": 85,
            },
            "candlestick": {
                "signal": "BULLISH",
                "patterns": ["BULLISH_ENGULFING"],
                "support": 24100.0,
                "resistance": 24300.0,
            },
            "chart": {
                "signal": "BULLISH",
                "patterns": ["UPTREND_STRUCTURE"],
            },
            "volume": {
                "bias": "BULLISH",
                "relative_volume": 1.8,
                "volume_spike": True,
                "signals": ["VOLUME_SPIKE"],
            },
            "regime_aware_evidence": {
                "contextual_bias": "BULLISH",
                "relevant_signals": [
                    "MULTI_TIMEFRAME_TREND",
                    "VOLUME_SPIKE",
                ],
                "confirmations": [
                    "Volume confirms bullish setup."
                ],
                "warnings": [],
            },
        },
        "setup_trigger": {
            "status": "TRIGGERED",
            "direction": "BULLISH",
            "trigger_type": "BREAKOUT",
            "trigger_price": 24250.0,
        },
        "contract": {
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 24300.0,
            "expiry": "2026-07-30",
        },
    }


def test_builds_complete_snapshot():

    result = build_decision_snapshot(
        full_pipeline_result()
    )

    assert result["decision"] == "TRADE_ALLOWED"
    assert result["direction"] == "BULLISH"

    assert (
        result["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        result["market_regime"]
        == "TRENDING_BULLISH"
    )

    assert (
        result["timeframe_alignment"]
        == "FULL"
    )

    assert (
        result["technical_trend"]
        == "BULLISH"
    )

    assert result["volume_bias"] == "BULLISH"
    assert result["relative_volume"] == 1.8
    assert result["volume_spike"] is True

    assert result["setup_status"] == "TRIGGERED"
    assert result["trigger_type"] == "BREAKOUT"

    assert (
        result["option_symbol"]
        == "NIFTY_TEST_CE"
    )

    assert result["option_type"] == "CE"


def test_missing_optional_sections_are_safe():

    result = build_decision_snapshot({
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
    })

    assert result["strategy"] is None
    assert result["market_regime"] is None
    assert result["volume_bias"] is None
    assert result["relative_volume"] is None

    assert result["risk_flags"] == []
    assert result["volume_signals"] == []
    assert result["confirmations"] == []
    assert result["warnings"] == []


def test_input_is_not_mutated():

    pipeline_result = (
        full_pipeline_result()
    )

    original = deepcopy(
        pipeline_result
    )

    build_decision_snapshot(
        pipeline_result
    )

    assert pipeline_result == original


def test_snapshot_lists_are_independent_copies():

    pipeline_result = (
        full_pipeline_result()
    )

    snapshot = build_decision_snapshot(
        pipeline_result
    )

    snapshot[
        "volume_signals"
    ].append(
        "EXTERNAL_MUTATION"
    )

    assert (
        "EXTERNAL_MUTATION"
        not in pipeline_result[
            "market_analysis"
        ][
            "volume"
        ][
            "signals"
        ]
    )


def test_invalid_input_fails_closed():

    with pytest.raises(
        ValueError,
        match=(
            "pipeline_result must be a dictionary"
        ),
    ):
        build_decision_snapshot(
            None
        )