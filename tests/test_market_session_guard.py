from datetime import datetime

import pytest

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)

from services.market_session_guard import (
    INDIA_TIMEZONE,
    evaluate_market_session,
)


def india_datetime(
    year,
    month,
    day,
    hour,
    minute,
):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=INDIA_TIMEZONE,
    )


def test_market_is_open_during_weekday_session():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        )
    )

    assert result["allowed"] is True
    assert result["market_open"] is True
    assert result["is_market_holiday"] is False
    assert result["status"] == "SESSION_VALID"


def test_market_is_closed_before_open():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            9,
            0,
        )
    )

    assert result["allowed"] is False
    assert result["market_open"] is False
    assert result["status"] == "MARKET_CLOSED"


def test_market_is_closed_after_close():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            15,
            31,
        )
    )

    assert result["allowed"] is False
    assert result["market_open"] is False
    assert result["status"] == "MARKET_CLOSED"


def test_market_is_closed_on_weekend():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            11,
            10,
            30,
        )
    )

    assert result["allowed"] is False
    assert result["market_open"] is False
    assert result["is_weekday"] is False
    assert result["status"] == "MARKET_CLOSED"


def test_recent_candle_is_fresh():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            10,
        ),
        candle_timestamp=india_datetime(
            2026,
            7,
            10,
            10,
            5,
        ),
        maximum_candle_age_minutes=10,
    )

    assert result["allowed"] is True
    assert result["candle_fresh"] is True
    assert result["candle_age_minutes"] == 5.0
    assert result["status"] == "SESSION_VALID"


def test_stale_candle_blocks_authorization():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
        candle_timestamp=india_datetime(
            2026,
            7,
            10,
            10,
            5,
        ),
        maximum_candle_age_minutes=10,
    )

    assert result["allowed"] is False
    assert result["market_open"] is True
    assert result["candle_fresh"] is False
    assert result["status"] == "STALE_MARKET_DATA"


def test_future_candle_is_rejected():

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            0,
        ),
        candle_timestamp=india_datetime(
            2026,
            7,
            10,
            10,
            5,
        ),
    )

    assert result["allowed"] is False
    assert result["candle_fresh"] is False
    assert result["status"] == "STALE_MARKET_DATA"


def test_invalid_maximum_candle_age():

    with pytest.raises(
        ValueError,
        match="maximum_candle_age_minutes",
    ):
        evaluate_market_session(
            maximum_candle_age_minutes=0,
        )


def test_configured_market_holiday_blocks_session():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-07-10",
        ]
    )

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
        holiday_calendar=calendar,
    )

    assert result["allowed"] is False
    assert result["market_open"] is False
    assert result["is_weekday"] is True
    assert result["is_market_holiday"] is True
    assert result["status"] == "MARKET_HOLIDAY"


def test_non_holiday_weekday_remains_open():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-07-09",
        ]
    )

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
        holiday_calendar=calendar,
    )

    assert result["allowed"] is True
    assert result["market_open"] is True
    assert result["is_market_holiday"] is False
    assert result["status"] == "SESSION_VALID"


def test_holiday_status_takes_priority_over_stale_data():

    calendar = MarketHolidayCalendar(
        holidays=[
            "2026-07-10",
        ]
    )

    result = evaluate_market_session(
        now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
        candle_timestamp=india_datetime(
            2026,
            7,
            10,
            9,
            30,
        ),
        maximum_candle_age_minutes=10,
        holiday_calendar=calendar,
    )

    assert result["allowed"] is False
    assert result["market_open"] is False
    assert result["is_market_holiday"] is True
    assert result["candle_fresh"] is False
    assert result["status"] == "MARKET_HOLIDAY"