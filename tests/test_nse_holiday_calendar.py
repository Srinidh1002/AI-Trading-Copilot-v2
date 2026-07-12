from services.nse_holiday_calendar import (
    NSE_TRADING_HOLIDAYS_2026,
    get_nse_holiday_calendar,
)


def test_nse_2026_holiday_count():

    assert len(
        NSE_TRADING_HOLIDAYS_2026
    ) == 16


def test_republic_day_is_nse_holiday():

    calendar = (
        get_nse_holiday_calendar()
    )

    assert calendar.is_holiday(
        "2026-01-26"
    ) is True


def test_regular_trading_day_is_not_holiday():

    calendar = (
        get_nse_holiday_calendar()
    )

    assert calendar.is_holiday(
        "2026-07-10"
    ) is False


def test_additional_january_closure_is_holiday():

    calendar = (
        get_nse_holiday_calendar()
    )

    assert calendar.is_holiday(
        "2026-01-15"
    ) is True


def test_christmas_is_nse_holiday():

    calendar = (
        get_nse_holiday_calendar()
    )

    assert calendar.is_holiday(
        "2026-12-25"
    ) is True