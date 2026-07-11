import pandas as pd
import pytest

from services.data_normalizer import normalize_angel_candles


def test_normalize_angel_candles():

    candles = [
        [
            "2026-07-10T09:15:00+05:30",
            24124.7,
            24187.9,
            24120.35,
            24162.7,
            0,
        ],
        [
            "2026-07-10T09:20:00+05:30",
            24165.85,
            24178.2,
            24154.3,
            24174.75,
            0,
        ],
    ]

    df = normalize_angel_candles(candles)

    assert isinstance(df, pd.DataFrame)

    assert list(df.columns) == [
        "timestamp",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    assert len(df) == 2
    assert df.iloc[0]["Close"] == 24162.7


def test_empty_candles():

    with pytest.raises(
        ValueError,
        match="No candle data provided",
    ):
        normalize_angel_candles([])
        