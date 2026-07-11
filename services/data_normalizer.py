"""
Normalize broker market data into a standard OHLCV DataFrame.
"""

import pandas as pd


CANDLE_COLUMNS = [
    "timestamp",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]


def normalize_angel_candles(candles):
    """
    Convert Angel One candle data into a standard OHLCV DataFrame.
    """

    if not candles:
        raise ValueError("No candle data provided.")

    df = pd.DataFrame(
        candles,
        columns=CANDLE_COLUMNS,
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    numeric_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "timestamp",
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )

    df = (
        df.sort_values("timestamp")
        .drop_duplicates(
            subset=["timestamp"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return df