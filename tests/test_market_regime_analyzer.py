import pandas as pd
import pytest

from services.market_regime_analyzer import (
    analyse_market_regime,
)


def make_data(
    close,
    ema20,
    ema50,
    atr,
    adx,
    bb_upper,
    bb_lower,
):
    return pd.DataFrame({
        "Close": [close],
        "EMA20": [ema20],
        "EMA50": [ema50],
        "ATR": [atr],
        "ADX": [adx],
        "BB_UPPER": [bb_upper],
        "BB_LOWER": [bb_lower],
    })


def test_trending_bullish():

    data = make_data(
        100,
        95,
        90,
        1,
        35,
        110,
        90,
    )

    result = analyse_market_regime(data)

    assert (
        result["primary_regime"]
        == "TRENDING_BULLISH"
    )

    assert result["trend"] == "BULLISH"


def test_trending_bearish():

    data = make_data(
        90,
        95,
        100,
        1,
        35,
        105,
        80,
    )

    result = analyse_market_regime(data)

    assert (
        result["primary_regime"]
        == "TRENDING_BEARISH"
    )

    assert result["trend"] == "BEARISH"


def test_high_volatility():

    data = make_data(
        100,
        101,
        99,
        3,
        22,
        115,
        85,
    )

    result = analyse_market_regime(data)

    assert (
        result["primary_regime"]
        == "HIGH_VOLATILITY"
    )


def test_compression():

    data = make_data(
        100,
        100,
        100,
        0.4,
        15,
        100.8,
        99.2,
    )

    result = analyse_market_regime(data)

    assert (
        result["primary_regime"]
        == "COMPRESSION"
    )


def test_empty_data():

    with pytest.raises(
        ValueError,
        match="No market data provided",
    ):
        analyse_market_regime(
            pd.DataFrame()
        )


def test_missing_columns():

    data = pd.DataFrame({
        "Close": [100]
    })

    with pytest.raises(ValueError):
        analyse_market_regime(data)