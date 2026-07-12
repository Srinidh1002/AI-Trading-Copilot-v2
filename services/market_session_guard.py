"""
Market session, holiday, and data-freshness safety guard.

Checks:
- Whether the current day is a weekday
- Whether the current day is a configured trading holiday
- Whether the current time is inside regular Indian market hours
- Whether the latest completed candle is fresh enough

This module does not place orders.
"""

from datetime import (
    datetime,
    time,
)

from zoneinfo import ZoneInfo

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)
from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)

INDIA_TIMEZONE = ZoneInfo(
    "Asia/Kolkata"
)

MARKET_OPEN_TIME = time(
    hour=9,
    minute=15,
)

MARKET_CLOSE_TIME = time(
    hour=15,
    minute=30,
)


def _normalize_datetime(
    value,
):
    """
    Convert a datetime or ISO timestamp
    into an India-timezone-aware datetime.
    """

    if isinstance(
        value,
        datetime,
    ):
        parsed = value

    else:
        cleaned = str(
            value
        ).strip()

        if not cleaned:
            raise ValueError(
                "Timestamp cannot be empty."
            )

        parsed = datetime.fromisoformat(
            cleaned.replace(
                "Z",
                "+00:00",
            )
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=INDIA_TIMEZONE
        )

    else:
        parsed = parsed.astimezone(
            INDIA_TIMEZONE
        )

    return parsed


def evaluate_market_session(
    now=None,
    candle_timestamp=None,
    maximum_candle_age_minutes=10,
    holiday_calendar=None,
):
    """
    Evaluate:
    - Trading weekday
    - Configured market holiday
    - Regular market hours
    - Candle freshness

    Returns a structured safety result.

    Possible statuses:
    - SESSION_VALID
    - MARKET_CLOSED
    - MARKET_HOLIDAY
    - STALE_MARKET_DATA
    """

    if maximum_candle_age_minutes <= 0:
        raise ValueError(
            "maximum_candle_age_minutes must "
            "be greater than zero."
        )

    current_time = (
        _normalize_datetime(
            now
        )
        if now is not None
        else datetime.now(
            INDIA_TIMEZONE
        )
    )

    reasons = []

    # ---------------------------------
    # WEEKDAY CHECK
    # ---------------------------------

    is_weekday = (
        current_time.weekday()
        < 5
    )

    if not is_weekday:
        reasons.append(
            "Market is closed because today "
            "is not a trading weekday."
        )

    # ---------------------------------
    # HOLIDAY CHECK
    # ---------------------------------

    if holiday_calendar is None:
        holiday_calendar = (
            MarketHolidayCalendar()
        )

    is_market_holiday = (
        holiday_calendar.is_holiday(
            current_time
        )
    )

    if is_market_holiday:
        reasons.append(
            "Market is closed because today "
            "is a configured trading holiday."
        )

    # ---------------------------------
    # MARKET HOURS CHECK
    # ---------------------------------

    current_clock_time = (
        current_time.time()
        .replace(
            tzinfo=None
        )
    )

    within_market_hours = (
        MARKET_OPEN_TIME
        <= current_clock_time
        <= MARKET_CLOSE_TIME
    )

    market_open = (
        is_weekday
        and not is_market_holiday
        and within_market_hours
    )

    if (
        is_weekday
        and not is_market_holiday
        and not within_market_hours
    ):
        reasons.append(
            "Current time is outside regular "
            "market hours."
        )

    # ---------------------------------
    # CANDLE FRESHNESS CHECK
    # ---------------------------------

    candle_fresh = None
    candle_age_minutes = None
    normalized_candle_time = None

    if candle_timestamp is not None:

        normalized_candle_time = (
            _normalize_datetime(
                candle_timestamp
            )
        )

        candle_age_seconds = (
            current_time
            - normalized_candle_time
        ).total_seconds()

        candle_age_minutes = (
            candle_age_seconds
            / 60
        )

        if candle_age_minutes < 0:

            candle_fresh = False

            reasons.append(
                "Candle timestamp is in the future."
            )

        elif (
            candle_age_minutes
            <= maximum_candle_age_minutes
        ):

            candle_fresh = True

        else:

            candle_fresh = False

            reasons.append(
                "Latest completed candle is stale."
            )

    # ---------------------------------
    # FINAL SAFETY STATUS
    # ---------------------------------

    allowed = (
        market_open
        and (
            candle_fresh is not False
        )
    )

    if is_market_holiday:
        status = "MARKET_HOLIDAY"

    elif not market_open:
        status = "MARKET_CLOSED"

    elif candle_fresh is False:
        status = "STALE_MARKET_DATA"

    else:
        status = "SESSION_VALID"

    return {
        "allowed": allowed,
        "status": status,
        "market_open": market_open,
        "is_weekday": is_weekday,
        "is_market_holiday": (
            is_market_holiday
        ),
        "within_market_hours": (
            within_market_hours
        ),
        "current_time": (
            current_time.isoformat()
        ),
        "market_open_time": "09:15",
        "market_close_time": "15:30",
        "candle_timestamp": (
            normalized_candle_time.isoformat()
            if normalized_candle_time
            is not None
            else None
        ),
        "candle_age_minutes": (
            round(
                candle_age_minutes,
                2,
            )
            if candle_age_minutes
            is not None
            else None
        ),
        "candle_fresh": candle_fresh,
        "maximum_candle_age_minutes": (
            maximum_candle_age_minutes
        ),
        "reasons": reasons,
    }