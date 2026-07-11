import pandas as pd
import pytest

from services.live_readiness_checker import (
    check_live_readiness,
)


def make_data(rows):
    return pd.DataFrame({
        "Close": range(rows)
    })


def test_all_timeframes_ready():

    timeframes = {
        "5m": make_data(250),
        "15m": make_data(250),
        "1h": make_data(150),
        "1d": make_data(150),
    }

    result = check_live_readiness(
        timeframes
    )

    assert result["ready"] is True
    assert result["reasons"] == []


def test_insufficient_candles():

    timeframes = {
        "5m": make_data(50),
        "15m": make_data(250),
        "1h": make_data(150),
        "1d": make_data(150),
    }

    result = check_live_readiness(
        timeframes
    )

    assert result["ready"] is False
    assert (
        result["checks"]["5m"]["ready"]
        is False
    )


def test_missing_timeframe():

    timeframes = {
        "5m": make_data(250),
    }

    result = check_live_readiness(
        timeframes
    )

    assert result["ready"] is False

    assert (
        "15m timeframe is missing."
        in result["reasons"]
    )


def test_empty_input():

    with pytest.raises(
        ValueError,
        match="No timeframe data provided",
    ):
        check_live_readiness({})