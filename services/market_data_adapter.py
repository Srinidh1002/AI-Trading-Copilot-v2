"""
Market-data column adapter.

Provides consistent uppercase and lowercase OHLCV formats
without changing the existing analyzers.
"""


def to_uppercase_ohlcv(data):
    if data is None or data.empty:
        return data

    df = data.copy()

    mapping = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }

    return df.rename(
        columns={
            old: new
            for old, new in mapping.items()
            if old in df.columns
        }
    )


def to_lowercase_ohlcv(data):
    if data is None or data.empty:
        return data

    df = data.copy()

    mapping = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }

    return df.rename(
        columns={
            old: new
            for old, new in mapping.items()
            if old in df.columns
        }
    )