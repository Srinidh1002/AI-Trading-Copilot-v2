"""
BSE trading holiday calendar.

Configured from the official BSE 2026 trading holiday
schedule for the Equity and Equity Derivatives segments.

Weekend closures remain handled separately by
market_session_guard.py.

Special trading sessions with non-standard hours must
be handled separately from the regular holiday calendar.
"""

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)


BSE_TRADING_HOLIDAYS_2026 = [
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


def get_bse_holiday_calendar():
    """
    Return the configured BSE trading holiday calendar.
    """

    return MarketHolidayCalendar(
        holidays=BSE_TRADING_HOLIDAYS_2026
    )
