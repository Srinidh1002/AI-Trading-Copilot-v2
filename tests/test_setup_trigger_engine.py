import pytest

from services.setup_trigger_engine import (
    evaluate_setup_trigger,
)


def bullish_strategy(
    decision="NO_TRADE",
):
    return {
        "strategy": "NO_TRADE",
        "direction": "BULLISH",
        "decision": decision,
        "confidence": 100,
        "risk_flags": [],
    }


def bearish_strategy(
    decision="NO_TRADE",
):
    return {
        "strategy": "NO_TRADE",
        "direction": "BEARISH",
        "decision": decision,
        "confidence": 90,
        "risk_flags": [],
    }


def test_waiting_for_bullish_breakout():

    result = evaluate_setup_trigger(
        strategy=bullish_strategy(),
        chart={
            "patterns": [
                "DOUBLE_BOTTOM",
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 24173.60,
            "resistance": 24228.45,
        },
        current_price=24206.90,
    )

    assert (
        result["status"]
        == "WAITING_FOR_BREAKOUT"
    )

    assert (
        result["triggered"]
        is False
    )

    assert (
        result["trigger_price"]
        == 24228.45
    )


def test_bullish_breakout_is_triggered():

    result = evaluate_setup_trigger(
        strategy=bullish_strategy(),
        chart={
            "patterns": [
                "DOUBLE_BOTTOM",
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 24173.60,
            "resistance": 24228.45,
        },
        current_price=24230.00,
    )

    assert (
        result["status"]
        == "TRIGGERED"
    )

    assert (
        result["triggered"]
        is True
    )

    assert (
        result["trigger_type"]
        == "BREAKOUT"
    )


def test_waiting_for_bearish_breakdown():

    result = evaluate_setup_trigger(
        strategy=bearish_strategy(),
        chart={
            "patterns": [
                "DOUBLE_TOP",
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 24173.60,
            "resistance": 24228.45,
        },
        current_price=24200.00,
    )

    assert (
        result["status"]
        == "WAITING_FOR_BREAKDOWN"
    )

    assert (
        result["triggered"]
        is False
    )

    assert (
        result["trigger_price"]
        == 24173.60
    )


def test_bearish_breakdown_is_triggered():

    result = evaluate_setup_trigger(
        strategy=bearish_strategy(),
        chart={
            "patterns": [
                "DOUBLE_TOP",
            ]
        },
        candlestick={
            "support": 24173.60,
            "resistance": 24228.45,
        },
        current_price=24170.00,
    )

    assert (
        result["status"]
        == "TRIGGERED"
    )

    assert (
        result["triggered"]
        is True
    )

    assert (
        result["trigger_type"]
        == "BREAKDOWN"
    )


def test_neutral_direction_returns_no_setup():

    result = evaluate_setup_trigger(
        strategy={
            "direction": "NEUTRAL",
            "decision": "NO_TRADE",
            "confidence": 0,
            "risk_flags": [],
        },
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=105,
    )

    assert (
        result["status"]
        == "NO_SETUP"
    )


def test_risk_flags_block_setup():

    strategy = bullish_strategy()

    strategy["risk_flags"] = [
        "Conflicting timeframe signals"
    ]

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "DOUBLE_BOTTOM",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=105,
    )

    assert (
        result["status"]
        == "NO_SETUP"
    )

    assert (
        result["triggered"]
        is False
    )


def test_missing_resistance_returns_no_setup():

    result = evaluate_setup_trigger(
        strategy=bullish_strategy(),
        chart={
            "patterns": [
                "DOUBLE_BOTTOM",
            ]
        },
        candlestick={
            "support": 100,
        },
        current_price=105,
    )

    assert (
        result["status"]
        == "NO_SETUP"
    )


def test_breakout_buffer_is_applied():

    result = evaluate_setup_trigger(
        strategy=bullish_strategy(),
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=110.05,
        breakout_buffer_percent=0.1,
    )

    assert (
        result["status"]
        == "WAITING_FOR_BREAKOUT"
    )

    assert (
        result["trigger_price"]
        == 110.11
    )


def test_invalid_current_price():

    with pytest.raises(
        ValueError,
        match=(
            "current_price must be "
            "greater than zero"
        ),
    ):
        evaluate_setup_trigger(
            strategy=bullish_strategy(),
            chart={},
            candlestick={},
            current_price=0,
        )


def test_negative_breakout_buffer():

    with pytest.raises(
        ValueError,
        match=(
            "breakout_buffer_percent "
            "cannot be negative"
        ),
    ):
        evaluate_setup_trigger(
            strategy=bullish_strategy(),
            chart={},
            candlestick={},
            current_price=100,
            breakout_buffer_percent=-1,
        )

def test_direction_confidence_takes_precedence_over_legacy_confidence():

    strategy = bullish_strategy()

    strategy["direction_confidence"] = 64
    strategy["confidence"] = 100

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=105,
    )

    assert result["confidence"] == 64


def test_legacy_confidence_remains_supported():

    strategy = bullish_strategy()

    assert (
        "direction_confidence"
        not in strategy
    )

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=105,
    )

    assert result["confidence"] == 100

def test_setup_formation_near_trigger():

    strategy = bullish_strategy()

    strategy["direction_confidence"] = 80
    strategy["evidence_strength_score"] = 80

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=109.95,
    )

    assert (
        result["formation_status"]
        == "NEAR_TRIGGER"
    )

    assert (
        result["setup_maturity_score"]
        == 100
    )

    assert (
        result["distance_to_trigger"]
        == 0.05
    )


def test_setup_formation_developing():

    strategy = bullish_strategy()

    strategy["direction_confidence"] = 60
    strategy["evidence_strength_score"] = 40

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=108,
    )

    assert (
        result["formation_status"]
        == "DEVELOPING"
    )

    assert (
        result["setup_maturity_score"]
        == 70
    )


def test_setup_formation_early_without_chart_evidence():

    strategy = bullish_strategy()

    strategy["direction_confidence"] = 30
    strategy["evidence_strength_score"] = 10

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [],
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=100,
    )

    assert (
        result["formation_status"]
        == "EARLY_FORMATION"
    )

    assert (
        result["setup_maturity_score"]
        == 25
    )


def test_triggered_setup_has_full_maturity():

    strategy = bullish_strategy()

    strategy["direction_confidence"] = 80
    strategy["evidence_strength_score"] = 80

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=111,
    )

    assert (
        result["formation_status"]
        == "TRIGGERED"
    )

    assert (
        result["setup_maturity_score"]
        == 100
    )


def test_risk_blocked_setup_exposes_blocked_formation():

    strategy = bullish_strategy()

    strategy["risk_flags"] = [
        "Conflicting timeframe signals"
    ]

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=109,
    )

    assert (
        result["formation_status"]
        == "BLOCKED"
    )

    assert (
        result["triggered"]
        is False
    )


def test_setup_formation_does_not_authorize_trade():

    strategy = bullish_strategy(
        decision="NO_TRADE"
    )

    strategy["direction_confidence"] = 100
    strategy["evidence_strength_score"] = 100

    result = evaluate_setup_trigger(
        strategy=strategy,
        chart={
            "patterns": [
                "CONSOLIDATION",
            ]
        },
        candlestick={
            "support": 100,
            "resistance": 110,
        },
        current_price=109.99,
    )

    assert (
        result["formation_status"]
        == "NEAR_TRIGGER"
    )

    assert (
        result["status"]
        == "WAITING_FOR_BREAKOUT"
    )

    assert result["triggered"] is False
