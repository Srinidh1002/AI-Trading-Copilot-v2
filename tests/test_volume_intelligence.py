import pandas as pd
import pytest

from services.volume_intelligence import (
    analyse_volume_intelligence,
)


def make_data(
    closes,
    volumes,
):
    return pd.DataFrame({
        "open": closes,
        "high": [
            value + 1
            for value in closes
        ],
        "low": [
            value - 1
            for value in closes
        ],
        "close": closes,
        "volume": volumes,
    })


def test_detects_volume_spike():

    df = make_data(
        [100, 101, 102, 103, 104],
        [100, 100, 100, 100, 200],
    )

    result = analyse_volume_intelligence(
        df,
        spike_threshold=1.5,
    )

    assert result["volume_spike"] is True
    assert result["relative_volume"] == 2.0


def test_reports_relative_volume_for_zero_volume_history():

    df = make_data(
        [100, 101, 102],
        [0, 0, 0],
    )

    result = analyse_volume_intelligence(df)

    assert result["relative_volume"] == 0.0
    assert result["volume_spike"] is False


def test_detects_rising_price_falling_volume():

    df = make_data(
        [100, 102, 104, 106, 108],
        [500, 400, 300, 200, 100],
    )

    result = analyse_volume_intelligence(
        df
    )

    assert (
        result["divergence"]
        == "BEARISH_WARNING"
    )

    assert result["bias"] == "BEARISH"


def test_detects_falling_price_falling_volume():

    df = make_data(
        [108, 106, 104, 102, 100],
        [500, 400, 300, 200, 100],
    )

    result = analyse_volume_intelligence(
        df
    )

    assert (
        result["divergence"]
        == "SELLING_PRESSURE_FADING"
    )

    assert result["bias"] == "BULLISH"


def test_detects_high_volume_near_support():

    df = make_data(
        [105, 104, 103, 102, 100.1],
        [100, 100, 100, 100, 300],
    )

    result = analyse_volume_intelligence(
        df,
        support=100,
        resistance=110,
    )

    assert result["near_support"] is True
    assert result["volume_spike"] is True

    assert (
        "HIGH_VOLUME_AT_SUPPORT"
        in result["signals"]
    )


def test_detects_high_volume_near_resistance():

    df = make_data(
        [105, 106, 107, 108, 109.9],
        [100, 100, 100, 100, 300],
    )

    result = analyse_volume_intelligence(
        df,
        support=100,
        resistance=110,
    )

    assert result["near_resistance"] is True

    assert (
        "HIGH_VOLUME_AT_RESISTANCE"
        in result["signals"]
    )


def test_confirms_breakout_with_volume():

    df = make_data(
        [105, 106, 107, 108, 111],
        [100, 100, 100, 100, 300],
    )

    result = analyse_volume_intelligence(
        df,
        support=100,
        resistance=110,
    )

    assert (
        result["breakout_confirmed"]
        is True
    )

    assert (
        "VOLUME_CONFIRMED_BREAKOUT"
        in result["signals"]
    )


def test_confirms_breakdown_with_volume():

    df = make_data(
        [105, 104, 103, 102, 99],
        [100, 100, 100, 100, 300],
    )

    result = analyse_volume_intelligence(
        df,
        support=100,
        resistance=110,
    )

    assert (
        result["breakdown_confirmed"]
        is True
    )

    assert (
        "VOLUME_CONFIRMED_BREAKDOWN"
        in result["signals"]
    )


def test_rejects_missing_columns():

    df = pd.DataFrame({
        "close": [100],
        "volume": [100],
    })

    with pytest.raises(
        ValueError,
        match="Missing required OHLCV columns",
    ):
        analyse_volume_intelligence(df)
