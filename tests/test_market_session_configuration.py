from datetime import datetime

from zoneinfo import ZoneInfo

from services.bse_holiday_calendar import (
    BSE_TRADING_HOLIDAYS_2026,
    get_bse_holiday_calendar,
)
from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)
from services.market_session_configuration import (
    MarketSessionConfiguration,
    resolve_market_session_configuration,
)
from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)


IST = ZoneInfo(
    "Asia/Kolkata"
)


def test_nifty_resolves_nse_session_configuration():
    configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    assert isinstance(
        configuration,
        MarketSessionConfiguration,
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )

    assert (
        configuration.exchange
        == "NSE"
    )

    assert (
        configuration.option_exchange
        == "NFO"
    )

    assert isinstance(
        configuration.holiday_calendar,
        MarketHolidayCalendar,
    )


def test_default_session_configuration_is_nifty_nse():
    configuration = (
        resolve_market_session_configuration()
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )

    assert (
        configuration.exchange
        == "NSE"
    )

    assert (
        configuration.option_exchange
        == "NFO"
    )


def test_sensex_resolves_bse_session_configuration():
    configuration = (
        resolve_market_session_configuration(
            "SENSEX"
        )
    )

    assert isinstance(
        configuration,
        MarketSessionConfiguration,
    )

    assert (
        configuration.underlying
        == "SENSEX"
    )

    assert (
        configuration.exchange
        == "BSE"
    )

    assert (
        configuration.option_exchange
        == "BFO"
    )

    assert isinstance(
        configuration.holiday_calendar,
        MarketHolidayCalendar,
    )


def test_bse_2026_calendar_contains_official_holidays():
    assert (
        BSE_TRADING_HOLIDAYS_2026
        == [
            "2026-01-15",
            "2026-01-26",
            "2026-03-03",
            "2026-03-26",
            "2026-03-31",
            "2026-04-03",
            "2026-04-14",
            "2026-05-01",
            "2026-05-28",
            "2026-06-26",
            "2026-09-14",
            "2026-10-02",
            "2026-10-20",
            "2026-11-10",
            "2026-11-24",
            "2026-12-25",
        ]
    )


def test_bse_calendar_recognizes_republic_day():
    calendar = (
        get_bse_holiday_calendar()
    )

    assert calendar.is_holiday(
        datetime(
            2026,
            1,
            26,
            10,
            0,
            tzinfo=IST,
        )
    )


def test_bse_calendar_does_not_mark_regular_day_as_holiday():
    calendar = (
        get_bse_holiday_calendar()
    )

    assert not calendar.is_holiday(
        datetime(
            2026,
            7,
            16,
            10,
            0,
            tzinfo=IST,
        )
    )


def test_nifty_and_sensex_use_distinct_calendar_instances():
    nifty_configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    sensex_configuration = (
        resolve_market_session_configuration(
            "SENSEX"
        )
    )

    assert (
        nifty_configuration.holiday_calendar
        is not
        sensex_configuration.holiday_calendar
    )


def test_direct_nse_and_bse_calendar_instances_are_distinct():
    nse_calendar = (
        get_nse_holiday_calendar()
    )

    bse_calendar = (
        get_bse_holiday_calendar()
    )

    assert (
        nse_calendar
        is not bse_calendar
    )


def test_unknown_underlying_is_rejected():
    try:
        resolve_market_session_configuration(
            "BANKNIFTY"
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Expected unknown underlying rejection."
        )


def test_session_configuration_is_immutable():
    configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    try:
        configuration.exchange = "BSE"

    except AttributeError:
        pass

    else:
        raise AssertionError(
            "Expected immutable session "
            "configuration."
        )
