"""Canonical market-data column adapters.

Normalizes supported OHLCV column-name variants without mutating the
source DataFrame.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


_UPPERCASE_SCHEMA = {
    "timestamp": "timestamp",
    "datetime": "timestamp",
    "date": "timestamp",
    "time": "timestamp",
    "open": "Open",
    "openprice": "Open",
    "open_price": "Open",
    "high": "High",
    "highprice": "High",
    "high_price": "High",
    "low": "Low",
    "lowprice": "Low",
    "low_price": "Low",
    "close": "Close",
    "closeprice": "Close",
    "close_price": "Close",
    "ltp": "Close",
    "lastprice": "Close",
    "last_price": "Close",
    "volume": "Volume",
    "vol": "Volume",
    "totalvolume": "Volume",
    "total_volume": "Volume",
}

_LOWERCASE_SCHEMA = {
    "timestamp": "timestamp",
    "datetime": "timestamp",
    "date": "timestamp",
    "time": "timestamp",
    "open": "open",
    "openprice": "open",
    "open_price": "open",
    "high": "high",
    "highprice": "high",
    "high_price": "high",
    "low": "low",
    "lowprice": "low",
    "low_price": "low",
    "close": "close",
    "closeprice": "close",
    "close_price": "close",
    "ltp": "close",
    "lastprice": "close",
    "last_price": "close",
    "volume": "volume",
    "vol": "volume",
    "totalvolume": "volume",
    "total_volume": "volume",
}


def _normalized_key(value: object) -> str:
    return (
        str(value)
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
        .lower()
    )


def _canonical_key(value: object) -> str:
    normalized = _normalized_key(value)

    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    return normalized


def _rename_columns(
    data: pd.DataFrame,
    schema: Mapping[str, str],
) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    if data.empty:
        return data.copy()

    rename_map: dict[object, str] = {}

    for column in data.columns:
        canonical = _canonical_key(column)

        target = schema.get(canonical)
        if target is None:
            target = schema.get(canonical.replace("_", ""))

        if target is not None:
            rename_map[column] = target

    result = data.rename(columns=rename_map).copy()

    duplicate_columns = result.columns[
        result.columns.duplicated()
    ].tolist()

    if duplicate_columns:
        raise ValueError(
            "Duplicate OHLCV columns after normalization: "
            f"{sorted(set(map(str, duplicate_columns)))}"
        )

    return result


def _validate_required(
    data: pd.DataFrame,
    required: tuple[str, ...],
    schema_name: str,
) -> pd.DataFrame:
    missing = [
        column
        for column in required
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"{schema_name} OHLCV normalization failed. "
            f"Missing columns: {missing}. "
            f"Available columns: {list(map(str, data.columns))}"
        )

    return data


def to_uppercase_ohlcv(
    data: pd.DataFrame,
    *,
    require_complete: bool = False,
) -> pd.DataFrame:
    result = _rename_columns(
        data,
        _UPPERCASE_SCHEMA,
    )

    if require_complete and not result.empty:
        _validate_required(
            result,
            (
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ),
            "uppercase",
        )

    return result


def to_lowercase_ohlcv(
    data: pd.DataFrame,
    *,
    require_complete: bool = False,
) -> pd.DataFrame:
    result = _rename_columns(
        data,
        _LOWERCASE_SCHEMA,
    )

    if require_complete and not result.empty:
        _validate_required(
            result,
            (
                "open",
                "high",
                "low",
                "close",
                "volume",
            ),
            "lowercase",
        )

    return result