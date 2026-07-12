"""
Market-data integrity validator.

Validates live prices and OHLCV candles before
they are trusted by the trading decision pipeline.

Checks:
- Numeric and positive prices
- Valid OHLC relationships
- Non-negative volume
- Candle timestamp presence
- Duplicate timestamps
- Chronological candle ordering
- Abnormal price jumps

Read-only.
No orders are placed.
"""

from datetime import datetime


class MarketDataValidationError(ValueError):
    """
    Raised when market data fails
    mandatory integrity validation.
    """


def _to_float(
    value,
    field_name,
):
    """
    Convert a value to a finite float.
    """

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MarketDataValidationError(
            f"{field_name} must be numeric."
        ) from exc

    if number != number:
        raise MarketDataValidationError(
            f"{field_name} cannot be NaN."
        )

    if number in {
        float("inf"),
        float("-inf"),
    }:
        raise MarketDataValidationError(
            f"{field_name} must be finite."
        )

    return number


def _normalize_timestamp(
    value,
):
    """
    Convert datetime or ISO timestamp
    into a datetime object.
    """

    if isinstance(
        value,
        datetime,
    ):
        return value

    if value is None:
        raise MarketDataValidationError(
            "Candle timestamp is required."
        )

    cleaned = str(
        value
    ).strip()

    if not cleaned:
        raise MarketDataValidationError(
            "Candle timestamp is required."
        )

    try:
        return datetime.fromisoformat(
            cleaned.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError as exc:
        raise MarketDataValidationError(
            "Candle timestamp must be a valid "
            "ISO datetime."
        ) from exc


def validate_live_price(
    price,
):
    """
    Validate a live market price.
    """

    normalized_price = _to_float(
        price,
        "Price",
    )

    if normalized_price <= 0:
        raise MarketDataValidationError(
            "Price must be greater than zero."
        )

    return normalized_price


def validate_candle(
    candle,
):
    """
    Validate one OHLCV candle.

    Returns a normalized candle.
    """

    if not isinstance(
        candle,
        dict,
    ):
        raise MarketDataValidationError(
            "Candle must be a dictionary."
        )

    timestamp = _normalize_timestamp(
        candle.get(
            "timestamp"
        )
    )

    open_price = _to_float(
        candle.get(
            "open"
        ),
        "Open",
    )

    high_price = _to_float(
        candle.get(
            "high"
        ),
        "High",
    )

    low_price = _to_float(
        candle.get(
            "low"
        ),
        "Low",
    )

    close_price = _to_float(
        candle.get(
            "close"
        ),
        "Close",
    )

    volume = _to_float(
        candle.get(
            "volume",
            0,
        ),
        "Volume",
    )

    for field_name, value in {
        "Open": open_price,
        "High": high_price,
        "Low": low_price,
        "Close": close_price,
    }.items():

        if value <= 0:
            raise MarketDataValidationError(
                f"{field_name} must be "
                "greater than zero."
            )

    if volume < 0:
        raise MarketDataValidationError(
            "Volume cannot be negative."
        )

    if high_price < low_price:
        raise MarketDataValidationError(
            "High cannot be below Low."
        )

    if high_price < max(
        open_price,
        close_price,
    ):
        raise MarketDataValidationError(
            "High cannot be below Open or Close."
        )

    if low_price > min(
        open_price,
        close_price,
    ):
        raise MarketDataValidationError(
            "Low cannot be above Open or Close."
        )

    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


def validate_candle_sequence(
    candles,
    maximum_price_jump_percent=20.0,
):
    """
    Validate a chronological sequence
    of OHLCV candles.

    Checks:
    - At least one candle exists
    - Every candle is structurally valid
    - No duplicate timestamps
    - Strict chronological ordering
    - No abnormal close-to-close jump

    Returns normalized candles.
    """

    if not isinstance(
        candles,
        (
            list,
            tuple,
        ),
    ):
        raise MarketDataValidationError(
            "Candles must be a list or tuple."
        )

    if not candles:
        raise MarketDataValidationError(
            "Candles cannot be empty."
        )

    if maximum_price_jump_percent <= 0:
        raise ValueError(
            "maximum_price_jump_percent must "
            "be greater than zero."
        )

    normalized = []

    previous_timestamp = None
    previous_close = None

    seen_timestamps = set()

    for candle in candles:

        validated = validate_candle(
            candle
        )

        timestamp = validated[
            "timestamp"
        ]

        close_price = validated[
            "close"
        ]

        if timestamp in seen_timestamps:
            raise MarketDataValidationError(
                "Duplicate candle timestamp detected."
            )

        seen_timestamps.add(
            timestamp
        )

        if (
            previous_timestamp is not None
            and timestamp
            <= previous_timestamp
        ):
            raise MarketDataValidationError(
                "Candles must be in strict "
                "chronological order."
            )

        if previous_close is not None:

            price_jump_percent = (
                abs(
                    close_price
                    - previous_close
                )
                / previous_close
                * 100
            )

            if (
                price_jump_percent
                > maximum_price_jump_percent
            ):
                raise MarketDataValidationError(
                    "Abnormal candle price jump "
                    "detected."
                )

        normalized.append(
            validated
        )

        previous_timestamp = timestamp
        previous_close = close_price

    return normalized