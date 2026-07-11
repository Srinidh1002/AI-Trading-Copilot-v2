import pytest

from services.trade_level_engine import (
    calculate_trade_levels,
)


def test_bullish_levels_use_atr():

    result = calculate_trade_levels(
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        option_premium=100,
        minimum_risk_reward=2,
        option_stop_percent=20,
    )

    assert (
        result["underlying_stop_loss"]
        == 24180
    )

    assert (
        result["underlying_target"]
        == 24240
    )

    assert (
        result["option_stop_loss"]
        == 80
    )

    assert (
        result["option_target"]
        == 140
    )


def test_bullish_support_can_widen_stop():

    result = calculate_trade_levels(
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        option_premium=100,
        support=24150,
    )

    assert (
        result["underlying_stop_loss"]
        == 24150
    )

    assert (
        result["underlying_risk_points"]
        == 50
    )


def test_bearish_levels_use_atr():

    result = calculate_trade_levels(
        direction="BEARISH",
        spot_price=24200,
        atr=20,
        option_premium=100,
        minimum_risk_reward=2,
    )

    assert (
        result["underlying_stop_loss"]
        == 24220
    )

    assert (
        result["underlying_target"]
        == 24160
    )

    # Long PE premium still has its
    # premium stop below entry.
    assert (
        result["option_stop_loss"]
        == 80
    )

    assert (
        result["option_target"]
        == 140
    )


def test_bearish_resistance_can_widen_stop():

    result = calculate_trade_levels(
        direction="BEARISH",
        spot_price=24200,
        atr=20,
        option_premium=100,
        resistance=24250,
    )

    assert (
        result["underlying_stop_loss"]
        == 24250
    )

    assert (
        result["underlying_risk_points"]
        == 50
    )


def test_rejects_invalid_direction():

    with pytest.raises(
        ValueError,
        match=(
            "direction must be "
            "BULLISH or BEARISH"
        ),
    ):
        calculate_trade_levels(
            direction="NEUTRAL",
            spot_price=24200,
            atr=20,
            option_premium=100,
        )


def test_rejects_invalid_option_stop_percent():

    with pytest.raises(
        ValueError,
        match=(
            "option_stop_percent must be "
            "between 0 and 100"
        ),
    ):
        calculate_trade_levels(
            direction="BULLISH",
            spot_price=24200,
            atr=20,
            option_premium=100,
            option_stop_percent=100,
        )