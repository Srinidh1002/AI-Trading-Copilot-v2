import pytest

from services.breakout_confirmation_engine import (
    confirm_breakout,
)


def test_bullish_breakout_confirmed():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=24228.45,
        candle_close=24235.00,
    )

    assert result["confirmed"] is True
    assert result["status"] == "CONFIRMED"
    assert result["trigger_type"] == "BREAKOUT"
    assert result["price_confirmed"] is True


def test_bullish_breakout_not_confirmed():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=24228.45,
        candle_close=24220.00,
    )

    assert result["confirmed"] is False
    assert result["status"] == "NOT_CONFIRMED"
    assert result["price_confirmed"] is False


def test_bearish_breakdown_confirmed():

    result = confirm_breakout(
        direction="BEARISH",
        trigger_price=24173.60,
        candle_close=24165.00,
    )

    assert result["confirmed"] is True
    assert result["trigger_type"] == "BREAKDOWN"


def test_bearish_breakdown_not_confirmed():

    result = confirm_breakout(
        direction="BEARISH",
        trigger_price=24173.60,
        candle_close=24180.00,
    )

    assert result["confirmed"] is False


def test_confirmation_buffer_blocks_weak_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=100.05,
        confirmation_buffer_percent=0.1,
    )

    assert result["confirmed"] is False
    assert result["confirmation_price"] == 100.1


def test_confirmation_buffer_allows_strong_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=100.20,
        confirmation_buffer_percent=0.1,
    )

    assert result["confirmed"] is True


def test_required_volume_confirms_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=101,
        current_volume=1500,
        average_volume=1000,
        minimum_volume_multiplier=1.2,
        require_volume=True,
    )

    assert result["confirmed"] is True
    assert result["volume_confirmed"] is True


def test_required_volume_rejects_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=101,
        current_volume=1100,
        average_volume=1000,
        minimum_volume_multiplier=1.2,
        require_volume=True,
    )

    assert result["confirmed"] is False
    assert result["volume_confirmed"] is False


def test_missing_required_volume_rejects_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=101,
        require_volume=True,
    )

    assert result["confirmed"] is False
    assert result["volume_confirmed"] is None


def test_required_bullish_momentum_confirms():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=101,
        momentum_signal="BULLISH",
        require_momentum=True,
    )

    assert result["confirmed"] is True
    assert result["momentum_confirmed"] is True


def test_wrong_momentum_rejects_breakout():

    result = confirm_breakout(
        direction="BULLISH",
        trigger_price=100,
        candle_close=101,
        momentum_signal="BEARISH",
        require_momentum=True,
    )

    assert result["confirmed"] is False
    assert result["momentum_confirmed"] is False


def test_invalid_direction():

    with pytest.raises(
        ValueError,
        match="direction must be BULLISH or BEARISH",
    ):
        confirm_breakout(
            direction="NEUTRAL",
            trigger_price=100,
            candle_close=101,
        )


def test_invalid_trigger_price():

    with pytest.raises(
        ValueError,
        match="trigger_price must be greater than zero",
    ):
        confirm_breakout(
            direction="BULLISH",
            trigger_price=0,
            candle_close=101,
        )


def test_invalid_candle_close():

    with pytest.raises(
        ValueError,
        match="candle_close must be greater than zero",
    ):
        confirm_breakout(
            direction="BULLISH",
            trigger_price=100,
            candle_close=0,
        )


def test_negative_confirmation_buffer():

    with pytest.raises(
        ValueError,
        match="confirmation_buffer_percent cannot be negative",
    ):
        confirm_breakout(
            direction="BULLISH",
            trigger_price=100,
            candle_close=101,
            confirmation_buffer_percent=-0.1,
        )