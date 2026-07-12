from datetime import datetime

import pytest

from services.market_data_validator import (
    MarketDataValidationError,
    validate_candle,
    validate_candle_sequence,
    validate_live_price,
)


def valid_candle(
    timestamp="2026-07-10T10:00:00+05:30",
    open_price=24200,
    high=24250,
    low=24180,
    close=24230,
    volume=10000,
):
    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def test_valid_live_price():

    result = validate_live_price(
        24206.9
    )

    assert result == 24206.9


def test_live_price_string_is_normalized():

    result = validate_live_price(
        "24206.9"
    )

    assert result == 24206.9


def test_zero_live_price_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="greater than zero",
    ):
        validate_live_price(
            0
        )


def test_negative_live_price_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="greater than zero",
    ):
        validate_live_price(
            -100
        )


def test_non_numeric_live_price_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="must be numeric",
    ):
        validate_live_price(
            "invalid"
        )


def test_nan_live_price_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="cannot be NaN",
    ):
        validate_live_price(
            float("nan")
        )


def test_infinite_live_price_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="must be finite",
    ):
        validate_live_price(
            float("inf")
        )


def test_valid_candle():

    result = validate_candle(
        valid_candle()
    )

    assert result["open"] == 24200.0
    assert result["high"] == 24250.0
    assert result["low"] == 24180.0
    assert result["close"] == 24230.0
    assert result["volume"] == 10000.0

    assert isinstance(
        result["timestamp"],
        datetime,
    )


def test_candle_must_be_dictionary():

    with pytest.raises(
        MarketDataValidationError,
        match="dictionary",
    ):
        validate_candle(
            []
        )


def test_missing_timestamp_rejected():

    candle = valid_candle()

    candle[
        "timestamp"
    ] = None

    with pytest.raises(
        MarketDataValidationError,
        match="timestamp is required",
    ):
        validate_candle(
            candle
        )


def test_invalid_timestamp_rejected():

    candle = valid_candle(
        timestamp="not-a-date"
    )

    with pytest.raises(
        MarketDataValidationError,
        match="valid ISO datetime",
    ):
        validate_candle(
            candle
        )


def test_negative_volume_rejected():

    candle = valid_candle(
        volume=-1
    )

    with pytest.raises(
        MarketDataValidationError,
        match="Volume cannot be negative",
    ):
        validate_candle(
            candle
        )


def test_high_below_low_rejected():

    candle = valid_candle(
        open_price=24200,
        high=24150,
        low=24180,
        close=24200,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="High cannot be below Low",
    ):
        validate_candle(
            candle
        )


def test_high_below_open_rejected():

    candle = valid_candle(
        open_price=24250,
        high=24240,
        low=24180,
        close=24200,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="High cannot be below Open or Close",
    ):
        validate_candle(
            candle
        )


def test_low_above_close_rejected():

    candle = valid_candle(
        open_price=24250,
        high=24300,
        low=24220,
        close=24200,
    )

    with pytest.raises(
        MarketDataValidationError,
        match="Low cannot be above Open or Close",
    ):
        validate_candle(
            candle
        )


def test_zero_ohlc_price_rejected():

    candle = valid_candle(
        low=0
    )

    with pytest.raises(
        MarketDataValidationError,
        match="Low must be greater than zero",
    ):
        validate_candle(
            candle
        )


def test_valid_candle_sequence():

    candles = [
        valid_candle(
            timestamp=(
                "2026-07-10T10:00:00+05:30"
            ),
            close=24200,
        ),
        valid_candle(
            timestamp=(
                "2026-07-10T10:05:00+05:30"
            ),
            open_price=24200,
            high=24280,
            low=24190,
            close=24250,
        ),
    ]

    result = validate_candle_sequence(
        candles
    )

    assert len(
        result
    ) == 2


def test_empty_candle_sequence_rejected():

    with pytest.raises(
        MarketDataValidationError,
        match="cannot be empty",
    ):
        validate_candle_sequence(
            []
        )


def test_duplicate_timestamp_rejected():

    candles = [
        valid_candle(),
        valid_candle(),
    ]

    with pytest.raises(
        MarketDataValidationError,
        match="Duplicate candle timestamp",
    ):
        validate_candle_sequence(
            candles
        )


def test_out_of_order_candles_rejected():

    candles = [
        valid_candle(
            timestamp=(
                "2026-07-10T10:05:00+05:30"
            )
        ),
        valid_candle(
            timestamp=(
                "2026-07-10T10:00:00+05:30"
            )
        ),
    ]

    with pytest.raises(
        MarketDataValidationError,
        match="strict chronological order",
    ):
        validate_candle_sequence(
            candles
        )


def test_abnormal_price_jump_rejected():

    candles = [
        valid_candle(
            timestamp=(
                "2026-07-10T10:00:00+05:30"
            ),
            open_price=100,
            high=105,
            low=95,
            close=100,
        ),
        valid_candle(
            timestamp=(
                "2026-07-10T10:05:00+05:30"
            ),
            open_price=150,
            high=160,
            low=145,
            close=155,
        ),
    ]

    with pytest.raises(
        MarketDataValidationError,
        match="Abnormal candle price jump",
    ):
        validate_candle_sequence(
            candles,
            maximum_price_jump_percent=20,
        )


def test_invalid_maximum_price_jump_percent():

    with pytest.raises(
        ValueError,
        match="maximum_price_jump_percent",
    ):
        validate_candle_sequence(
            [
                valid_candle()
            ],
            maximum_price_jump_percent=0,
        )