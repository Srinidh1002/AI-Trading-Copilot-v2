"""
NSE trading holiday calendar.

Contains configured NSE equity and equity-derivatives
market holidays for calendar year 2026.

Weekend closures are handled separately by
market_session_guard.py.

Muhurat Trading and other special trading sessions
must be handled separately because they may have
non-standard market hours.
"""

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)


NSE_TRADING_HOLIDAYS_2026 = [
    "2026-01-15",  # Municipal Corporation Election - Maharashtra
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-26",  # Shri Ram Navami
    "2026-03-31",  # Shri Mahavir Jayanti
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id
    "2026-06-26",  # Muharram
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-10",  # Diwali-Balipratipada
    "2026-11-24",  # Guru Nanak Dev Prakash Gurpurb
    "2026-12-25",  # Christmas
]


def get_nse_holiday_calendar():
    """
    Return the configured NSE trading holiday calendar.
    """

    return MarketHolidayCalendar(
        holidays=NSE_TRADING_HOLIDAYS_2026
    )