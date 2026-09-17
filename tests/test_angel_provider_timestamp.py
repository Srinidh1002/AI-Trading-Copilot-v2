from datetime import datetime, timedelta, timezone

import pytest

from services.paper_orchestration.angel_provider_timestamp import (
    IST,
    AngelProviderTimestampV1,
    parse_angel_provider_timestamp,
    validate_angel_quote_timestamp,
)


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)


def test_parses_angel_local_timestamp():
    result = parse_angel_provider_timestamp(
        "05-Aug-2026 14:59:30"
    )

    assert result == datetime(
        2026,
        8,
        5,
        14,
        59,
        30,
        tzinfo=IST,
    )


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-05T09:29:30+00:00",
        "2026-08-05T09:29:30Z",
        int(
            (
                NOW
                - timedelta(seconds=30)
            ).timestamp()
        ),
        int(
            (
                NOW
                - timedelta(seconds=30)
            ).timestamp()
            * 1000
        ),
    ],
)
def test_parses_supported_timestamp_forms(value):
    result = parse_angel_provider_timestamp(
        value
    )

    assert result.tzinfo is not None
    assert result.utcoffset() is not None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "bad",
        True,
        float("nan"),
    ],
)
def test_invalid_timestamp_fails_closed(value):
    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        parse_angel_provider_timestamp(value)


def test_naive_datetime_is_rejected():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        parse_angel_provider_timestamp(
            datetime(2026, 8, 5, 9, 30)
        )


@pytest.mark.parametrize(
    "field",
    [
        "exchFeedTime",
        "exchangeTimestamp",
        "timestamp",
    ],
)
def test_validates_supported_timestamp_fields(field):
    result = validate_angel_quote_timestamp(
        data={
            field: (
                NOW
                - timedelta(seconds=30)
            ).isoformat(),
        },
        received_at=NOW,
    )

    assert type(result) is AngelProviderTimestampV1
    assert result.timestamp_field == field
    assert result.age_seconds == 30.0


def test_freshness_boundaries_are_inclusive():
    stale_boundary = (
        validate_angel_quote_timestamp(
            data={
                "exchFeedTime": (
                    NOW
                    - timedelta(seconds=300)
                ).isoformat(),
            },
            received_at=NOW,
        )
    )

    future_boundary = (
        validate_angel_quote_timestamp(
            data={
                "exchFeedTime": (
                    NOW
                    + timedelta(seconds=5)
                ).isoformat(),
            },
            received_at=NOW,
        )
    )

    assert stale_boundary.age_seconds == 300.0
    assert future_boundary.age_seconds == -5.0


def test_stale_timestamp_fails_closed():
    with pytest.raises(
        ValueError,
        match="stale",
    ):
        validate_angel_quote_timestamp(
            data={
                "exchFeedTime": (
                    NOW
                    - timedelta(seconds=301)
                ).isoformat(),
            },
            received_at=NOW,
        )


def test_future_timestamp_fails_closed():
    with pytest.raises(
        ValueError,
        match="future skew",
    ):
        validate_angel_quote_timestamp(
            data={
                "exchFeedTime": (
                    NOW
                    + timedelta(seconds=6)
                ).isoformat(),
            },
            received_at=NOW,
        )


def test_policy_limits_can_be_overridden():
    result = validate_angel_quote_timestamp(
        data={
            "exchFeedTime": (
                NOW
                - timedelta(seconds=600)
            ).isoformat(),
        },
        received_at=NOW,
        maximum_age_seconds=600,
        maximum_future_skew_seconds=10,
    )

    assert result.age_seconds == 600.0


@pytest.mark.parametrize(
    "name,value",
    [
        ("maximum_age_seconds", -1),
        ("maximum_future_skew_seconds", -1),
        ("maximum_age_seconds", float("nan")),
        ("maximum_future_skew_seconds", True),
    ],
)
def test_invalid_policy_limits_are_rejected(
    name,
    value,
):
    kwargs = {
        "maximum_age_seconds": 300,
        "maximum_future_skew_seconds": 5,
    }
    kwargs[name] = value

    with pytest.raises(
        ValueError,
        match=name,
    ):
        validate_angel_quote_timestamp(
            data={
                "exchFeedTime": NOW.isoformat(),
            },
            received_at=NOW,
            **kwargs,
        )
