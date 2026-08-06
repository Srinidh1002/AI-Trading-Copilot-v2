"""Strict Angel One candle normalization into canonical OHLCV data."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd


CANDLE_COLUMNS = [
    "timestamp",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]


def _finite_number(
    value,
    *,
    field,
    row_index,
):
    if isinstance(value, bool):
        raise ValueError(
            f"Candle row {row_index} "
            f"contains invalid {field}."
        )

    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Candle row {row_index} "
            f"contains invalid {field}."
        ) from exc

    if not math.isfinite(result):
        raise ValueError(
            f"Candle row {row_index} "
            f"contains non-finite {field}."
        )

    return result


def _aware_timestamp(
    value,
    *,
    row_index,
):
    try:
        timestamp = pd.Timestamp(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Candle row {row_index} "
            "contains an invalid timestamp."
        ) from exc

    if pd.isna(timestamp):
        raise ValueError(
            f"Candle row {row_index} "
            "contains an invalid timestamp."
        )

    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
    ):
        raise ValueError(
            f"Candle row {row_index} "
            "timestamp must be timezone-aware."
        )

    return timestamp


def _normalize_row(
    row,
    *,
    row_index,
):
    if (
        not isinstance(row, Sequence)
        or isinstance(
            row,
            (
                str,
                bytes,
                bytearray,
            ),
        )
    ):
        raise ValueError(
            f"Candle row {row_index} "
            "must be a sequence."
        )

    if len(row) != 6:
        raise ValueError(
            f"Candle row {row_index} "
            "must contain exactly 6 values."
        )

    timestamp = _aware_timestamp(
        row[0],
        row_index=row_index,
    )

    open_price = _finite_number(
        row[1],
        field="open",
        row_index=row_index,
    )

    high_price = _finite_number(
        row[2],
        field="high",
        row_index=row_index,
    )

    low_price = _finite_number(
        row[3],
        field="low",
        row_index=row_index,
    )

    close_price = _finite_number(
        row[4],
        field="close",
        row_index=row_index,
    )

    volume = _finite_number(
        row[5],
        field="volume",
        row_index=row_index,
    )

    if volume < 0:
        raise ValueError(
            f"Candle row {row_index} "
            "contains negative volume."
        )

    if low_price > high_price:
        raise ValueError(
            f"Candle row {row_index} "
            "contains low above high."
        )

    if not (
        low_price
        <= open_price
        <= high_price
    ):
        raise ValueError(
            f"Candle row {row_index} "
            "contains open outside low/high."
        )

    if not (
        low_price
        <= close_price
        <= high_price
    ):
        raise ValueError(
            f"Candle row {row_index} "
            "contains close outside low/high."
        )

    return [
        timestamp,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
    ]


def normalize_angel_candles(
    candles,
):
    """Validate and convert Angel candle rows without silent repair."""

    if (
        not isinstance(candles, Sequence)
        or isinstance(
            candles,
            (
                str,
                bytes,
                bytearray,
            ),
        )
    ):
        raise ValueError(
            "Candle data must be a sequence."
        )

    if not candles:
        raise ValueError(
            "No candle data provided."
        )

    normalized_rows = []

    previous_timestamp = None

    for row_index, row in enumerate(
        candles
    ):
        normalized = _normalize_row(
            row,
            row_index=row_index,
        )

        timestamp = normalized[0]

        if (
            previous_timestamp is not None
            and timestamp
            <= previous_timestamp
        ):
            raise ValueError(
                "Candle timestamps must be "
                "strictly increasing and unique."
            )

        previous_timestamp = timestamp
        normalized_rows.append(
            normalized
        )

    return pd.DataFrame(
        normalized_rows,
        columns=CANDLE_COLUMNS,
    )
