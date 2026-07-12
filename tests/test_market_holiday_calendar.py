from datetime import (
    date,
    datetime,
)

import pytest

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)


def test_empty_calendar_has_no_holidays():

    calendar = MarketHolidayCalendar()

    assert (
        calendar.is_holiday(
            "2026-01-26"
        )
        is False
    )


def test_string_holiday_is_detected():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-01-26",
        ]
    )

    assert (
        calendar.is_holiday(
            "2026-01-26"
        )
        is True
    )


def test_date_object_is_supported():

    calendar = MarketHolidayCalendar(
        holidays=[
            date(
                2026,
                1,
                26,
            )
        ]
    )

    assert (
        calendar.is_holiday(
            date(
                2026,
                1,
                26,
            )
        )
        is True
    )


def test_datetime_object_is_supported():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-01-26",
        ]
    )

    assert (
        calendar.is_holiday(
            datetime(
                2026,
                1,
                26,
                10,
                30,
            )
        )
        is True
    )


def test_add_holiday():

    calendar = MarketHolidayCalendar()

    calendar.add_holiday(
        "2026-01-26"
    )

    assert (
        calendar.is_holiday(
            "2026-01-26"
        )
        is True
    )


def test_remove_holiday():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-01-26",
        ]
    )

    calendar.remove_holiday(
        "2026-01-26"
    )

    assert (
        calendar.is_holiday(
            "2026-01-26"
        )
        is False
    )


def test_get_holidays_returns_sorted_dates():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-12-25",
            "2026-01-26",
            "2026-08-15",
        ]
    )

    assert (
        calendar.get_holidays()
        == [
            "2026-01-26",
            "2026-08-15",
            "2026-12-25",
        ]
    )


def test_invalid_date_format_raises_error():

    calendar = MarketHolidayCalendar()

    with pytest.raises(
        ValueError,
        match=(
            "Holiday date must use "
            "YYYY-MM-DD format"
        ),
    ):
        calendar.add_holiday(
            "26-01-2026"
        )


def test_empty_date_raises_error():

    calendar = MarketHolidayCalendar()

    with pytest.raises(
        ValueError,
        match=(
            "Holiday date cannot be empty"
        ),
    ):
        calendar.add_holiday(
            ""
        )