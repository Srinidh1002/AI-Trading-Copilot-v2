import pandas as pd
import pytest
from unittest.mock import patch

from services.multi_timeframe_analyzer import analyse_multi_timeframe


def make_df():
    return pd.DataFrame({
        "Close": [100, 101, 102]
    })


@patch("services.multi_timeframe_analyzer.analyse_technical")
def test_all_timeframes_bullish(mock_analyse):

    mock_analyse.return_value = {
        "trend": "BULLISH"
    }

    result = analyse_multi_timeframe({
        "5m": make_df(),
        "15m": make_df(),
        "1h": make_df(),
        "1d": make_df(),
    })

    assert result["overall_trend"] == "BULLISH"
    assert result["alignment"] == "FULL"
    assert result["confidence"] == 100


@patch("services.multi_timeframe_analyzer.analyse_technical")
def test_all_timeframes_bearish(mock_analyse):

    mock_analyse.return_value = {
        "trend": "BEARISH"
    }

    result = analyse_multi_timeframe({
        "5m": make_df(),
        "15m": make_df(),
        "1h": make_df(),
        "1d": make_df(),
    })

    assert result["overall_trend"] == "BEARISH"
    assert result["alignment"] == "FULL"
    assert result["confidence"] == 100


@patch("services.multi_timeframe_analyzer.analyse_technical")
def test_conflicting_timeframes(mock_analyse):

    mock_analyse.side_effect = [
        {"trend": "BULLISH"},
        {"trend": "BEARISH"},
        {"trend": "BULLISH"},
        {"trend": "BEARISH"},
    ]

    result = analyse_multi_timeframe({
        "5m": make_df(),
        "15m": make_df(),
        "1h": make_df(),
        "1d": make_df(),
    })

    assert result["overall_trend"] == "MIXED"
    assert result["alignment"] == "CONFLICTED"


def test_empty_timeframes():

    with pytest.raises(
        ValueError,
        match="No timeframe data provided",
    ):
        analyse_multi_timeframe({})