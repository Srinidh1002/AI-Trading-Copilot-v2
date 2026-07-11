import pandas as pd

from services.market_data_adapter import (
    to_uppercase_ohlcv,
    to_lowercase_ohlcv,
)


def test_convert_to_lowercase():

    data = pd.DataFrame({
        "Open": [100],
        "High": [110],
        "Low": [90],
        "Close": [105],
        "Volume": [1000],
    })

    result = to_lowercase_ohlcv(data)

    assert "open" in result.columns
    assert "close" in result.columns


def test_convert_to_uppercase():

    data = pd.DataFrame({
        "open": [100],
        "high": [110],
        "low": [90],
        "close": [105],
        "volume": [1000],
    })

    result = to_uppercase_ohlcv(data)

    assert "Open" in result.columns
    assert "Close" in result.columns