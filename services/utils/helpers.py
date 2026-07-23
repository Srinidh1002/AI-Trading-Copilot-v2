"""
Helper Utilities

Common helper functions used throughout the
AI Trading Copilot.

Responsibilities
----------------
✓ Date & Time Helpers
✓ Number Formatting
✓ Percentage Calculations
✓ Safe Type Conversion
✓ Dictionary Helpers
✓ List Helpers
✓ String Helpers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import math


# ==================================================
# Date & Time
# ==================================================

def now() -> datetime:
    return datetime.now()


def now_string(
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    return datetime.now().strftime(fmt)


def today_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def timestamp() -> float:
    return datetime.now().timestamp()


# ==================================================
# Number Helpers
# ==================================================

def round_number(
    value: float,
    digits: int = 2,
) -> float:
    return round(value, digits)


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(value, maximum))


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:

    if denominator == 0:
        return default

    return numerator / denominator


def percentage(
    value: float,
    total: float,
) -> float:

    return safe_divide(
        value * 100,
        total,
    )


def percentage_change(
    old: float,
    new: float,
) -> float:

    if old == 0:
        return 0.0

    return ((new - old) / old) * 100


# ==================================================
# Formatting
# ==================================================

def currency(
    value: float,
) -> str:

    return f"₹{value:,.2f}"


def format_number(
    value: float,
    digits: int = 2,
) -> str:

    return f"{value:,.{digits}f}"


def format_percent(
    value: float,
) -> str:

    return f"{value:.2f}%"


# ==================================================
# Safe Conversion
# ==================================================

def to_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)
    except Exception:
        return default


def to_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)
    except Exception:
        return default


def to_bool(
    value: Any,
) -> bool:

    if isinstance(value, bool):
        return value

    return str(value).lower() in (

        "1",

        "true",

        "yes",

        "y",

        "on",

    )


# ==================================================
# Dictionary Helpers
# ==================================================

def merge_dicts(
    *dictionaries: dict,
) -> dict:

    merged = {}

    for dictionary in dictionaries:

        merged.update(dictionary)

    return merged


def remove_none(
    dictionary: dict,
) -> dict:

    return {

        key: value

        for key, value in dictionary.items()

        if value is not None

    }


# ==================================================
# List Helpers
# ==================================================

def unique(
    values: list[Any],
) -> list[Any]:

    return list(dict.fromkeys(values))


def flatten(
    values: list[list[Any]],
) -> list[Any]:

    return [

        item

        for sublist in values

        for item in sublist

    ]


def average(
    values: list[float],
) -> float:

    if not values:

        return 0.0

    return sum(values) / len(values)


def median(
    values: list[float],
) -> float:

    if not values:

        return 0.0

    ordered = sorted(values)

    n = len(ordered)

    mid = n // 2

    if n % 2 == 0:

        return (

            ordered[mid - 1]

            + ordered[mid]

        ) / 2

    return ordered[mid]


# ==================================================
# String Helpers
# ==================================================

def title_case(
    text: str,
) -> str:

    return text.title()


def snake_case(
    text: str,
) -> str:

    return (

        text.strip()

        .lower()

        .replace(" ", "_")

        .replace("-", "_")

    )


def clean_string(
    text: str,
) -> str:

    return " ".join(

        text.split()

    )


# ==================================================
# Validation
# ==================================================

def is_number(
    value: Any,
) -> bool:

    try:

        float(value)

        return True

    except Exception:

        return False


def is_finite(
    value: float,
) -> bool:

    return math.isfinite(value)


# ==================================================
# Miscellaneous
# ==================================================

def chunks(
    values: list[Any],
    size: int,
):

    for index in range(

        0,

        len(values),

        size,

    ):

        yield values[

            index:index + size

        ]


def summary() -> dict[str, Any]:

    return {

        "module": "Helper Utilities",

        "functions": 23,

        "status": "ready",

    }