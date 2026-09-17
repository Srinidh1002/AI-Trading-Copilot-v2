"""Shared Angel provider timestamp parsing and freshness validation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")
ANGEL_TIMESTAMP_FORMAT = "%d-%b-%Y %H:%M:%S"
DEFAULT_MAXIMUM_QUOTE_AGE_SECONDS = 300.0
DEFAULT_MAXIMUM_FUTURE_SKEW_SECONDS = 5.0
PROVIDER_TIMESTAMP_FIELDS = (
    "exchFeedTime",
    "exchangeTimestamp",
    "timestamp",
)


@dataclass(frozen=True, slots=True)
class AngelProviderTimestampV1:
    provider_timestamp: datetime
    received_at: datetime
    timestamp_field: str
    age_seconds: float

    def __post_init__(self) -> None:
        for name in (
            "provider_timestamp",
            "received_at",
        ):
            value = getattr(self, name)

            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(
                    f"{name} must be timezone-aware"
                )

        if (
            not isinstance(self.timestamp_field, str)
            or not self.timestamp_field.strip()
        ):
            raise ValueError(
                "timestamp_field must be non-empty"
            )

        if (
            isinstance(self.age_seconds, bool)
            or not isinstance(
                self.age_seconds,
                (int, float),
            )
            or not math.isfinite(
                float(self.age_seconds)
            )
        ):
            raise ValueError(
                "age_seconds must be finite"
            )

        object.__setattr__(
            self,
            "timestamp_field",
            self.timestamp_field.strip(),
        )
        object.__setattr__(
            self,
            "age_seconds",
            float(self.age_seconds),
        )


def _aware(
    value: object,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware"
        )

    return value


def parse_angel_provider_timestamp(
    value: object,
) -> datetime:
    if isinstance(value, datetime):
        parsed = value

    elif (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        numeric = float(value)

        if numeric > 100_000_000_000:
            numeric /= 1000.0

        try:
            parsed = datetime.fromtimestamp(
                numeric,
                tz=timezone.utc,
            )
        except (
            OSError,
            OverflowError,
            ValueError,
        ) as exc:
            raise ValueError(
                "provider timestamp is invalid."
            ) from exc

    elif isinstance(value, str) and value.strip():
        raw = value.strip()

        try:
            parsed = datetime.fromisoformat(
                raw.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            try:
                parsed = datetime.strptime(
                    raw,
                    ANGEL_TIMESTAMP_FORMAT,
                ).replace(
                    tzinfo=IST,
                )
            except ValueError as exc:
                raise ValueError(
                    "provider timestamp is invalid."
                ) from exc

    else:
        raise ValueError(
            "provider timestamp is missing."
        )

    return _aware(
        parsed,
        "provider timestamp",
    )


def validate_angel_quote_timestamp(
    *,
    data: Mapping[str, object],
    received_at: datetime,
    maximum_age_seconds: float = (
        DEFAULT_MAXIMUM_QUOTE_AGE_SECONDS
    ),
    maximum_future_skew_seconds: float = (
        DEFAULT_MAXIMUM_FUTURE_SKEW_SECONDS
    ),
) -> AngelProviderTimestampV1:
    if not isinstance(data, Mapping):
        raise TypeError(
            "data must be a mapping"
        )

    received = _aware(
        received_at,
        "received_at",
    )

    for name, value in (
        (
            "maximum_age_seconds",
            maximum_age_seconds,
        ),
        (
            "maximum_future_skew_seconds",
            maximum_future_skew_seconds,
        ),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ValueError(
                f"{name} must be finite and non-negative"
            )

    timestamp_field = next(
        (
            field
            for field in PROVIDER_TIMESTAMP_FIELDS
            if data.get(field) is not None
        ),
        None,
    )

    if timestamp_field is None:
        raise ValueError(
            "provider timestamp is missing."
        )

    provider_timestamp = (
        parse_angel_provider_timestamp(
            data[timestamp_field]
        )
    )

    age_seconds = (
        received
        - provider_timestamp
    ).total_seconds()

    if age_seconds > float(maximum_age_seconds):
        raise ValueError(
            "provider quote timestamp is stale."
        )

    if (
        age_seconds
        < -float(maximum_future_skew_seconds)
    ):
        raise ValueError(
            "provider quote timestamp exceeds "
            "allowed future skew."
        )

    return AngelProviderTimestampV1(
        provider_timestamp=provider_timestamp,
        received_at=received,
        timestamp_field=timestamp_field,
        age_seconds=age_seconds,
    )
