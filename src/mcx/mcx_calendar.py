"""Authoritative MCX session resolver.

Safety contract:
- new entries fail closed when calendar authority is unknown;
- new entries stop before the actual session close;
- an already-open PAPER position may continue to be monitored/closed during
  CLOSE_BUFFER until the real exchange session ends;
- full holidays/weekends remain exchange-closed;
- no Muhurat session is inferred without separately verified timings.
"""

from __future__ import annotations

from datetime import (
    date,
    datetime,
    time as dtime,
    timedelta,
)
from zoneinfo import ZoneInfo

from mcx.mcx_holidays import (
    EVENING_CLOSED,
    FULL,
    MORNING_CLOSED,
    holiday_record,
    is_calendar_year_authoritative,
)


IST = ZoneInfo(
    "Asia/Kolkata"
)

MORNING_OPEN = dtime(
    9,
    0,
)

EVENING_START = dtime(
    17,
    0,
)

NEW_ENTRY_BUFFER_MINUTES = 15


def _as_ist(now):
    if now is None:
        return datetime.now(
            IST
        )

    if not isinstance(
        now,
        datetime,
    ):
        raise TypeError(
            "now must be datetime"
        )

    if now.tzinfo is None:
        return now.replace(
            tzinfo=IST
        )

    return now.astimezone(
        IST
    )


def _is_us_dst(
    d: date,
):
    """US DST: second Sunday in March through first Sunday in November."""

    if (
        d.month < 3
        or d.month > 11
    ):
        return False

    if d.month == 3:
        sundays = [
            day
            for day in range(
                1,
                32,
            )
            if date(
                d.year,
                3,
                day,
            ).weekday() == 6
        ]

        return (
            d.day
            >= sundays[1]
        )

    if d.month == 11:
        first_sunday = next(
            day
            for day in range(
                1,
                8,
            )
            if date(
                d.year,
                11,
                day,
            ).weekday() == 6
        )

        return (
            d.day
            < first_sunday
        )

    return True


def _normal_close_time(
    d,
):
    # Internationally linked non-agricultural commodities:
    # 23:30 during US DST,
    # 23:55 outside US DST.
    return (
        dtime(
            23,
            30,
        )
        if _is_us_dst(d)
        else dtime(
            23,
            55,
        )
    )


def _minus_minutes(
    value,
    minutes,
):
    base = datetime.combine(
        date(
            2000,
            1,
            1,
        ),
        value,
    )

    result = (
        base
        - timedelta(
            minutes=minutes
        )
    )

    return result.time()


def _result(
    *,
    status,
    session_open,
    new_entries_allowed,
    position_management_allowed,
    close_time,
    note,
    phase=None,
    holiday_kind=None,
    holiday_name=None,
    calendar_authoritative=True,
):
    # tradable is retained as a compatibility alias for NEW ENTRY authority.
    return {
        "status": status,
        "tradable":
            bool(
                new_entries_allowed
            ),
        "session_open":
            bool(
                session_open
            ),
        "new_entries_allowed":
            bool(
                new_entries_allowed
            ),
        "position_management_allowed":
            bool(
                position_management_allowed
            ),
        "close_time":
            close_time,
        "note": note,
        "phase": phase,
        "holiday_kind":
            holiday_kind,
        "holiday_name":
            holiday_name,
        "calendar_authoritative":
            bool(
                calendar_authoritative
            ),
    }


def get_session(
    now=None,
):
    now = _as_ist(
        now
    )

    current_date = (
        now.date()
    )

    current_time = (
        now.time().replace(
            tzinfo=None
        )
    )

    if not is_calendar_year_authoritative(
        current_date.year
    ):
        return _result(
            status="CALENDAR_UNKNOWN",
            session_open=False,
            new_entries_allowed=False,
            position_management_allowed=False,
            close_time=None,
            note=(
                "authoritative MCX calendar "
                f"not loaded for {current_date.year}"
            ),
            calendar_authoritative=False,
        )

    # Weekend stays closed.
    #
    # 2026 Muhurat trading is deliberately NOT inferred from Sunday.
    # A separately verified special-session authority is required.
    if now.weekday() >= 5:
        return _result(
            status="WEEKEND",
            session_open=False,
            new_entries_allowed=False,
            position_management_allowed=False,
            close_time=None,
            note="Saturday/Sunday",
        )

    holiday = holiday_record(
        current_date.year,
        current_date.month,
        current_date.day,
    )

    holiday_kind = (
        holiday.get(
            "kind"
        )
        if holiday
        else None
    )

    holiday_name = (
        holiday.get(
            "name"
        )
        if holiday
        else None
    )

    if (
        holiday_kind
        == FULL
    ):
        return _result(
            status="HOLIDAY_FULL_CLOSED",
            session_open=False,
            new_entries_allowed=False,
            position_management_allowed=False,
            close_time=None,
            note=holiday_name,
            holiday_kind=holiday_kind,
            holiday_name=holiday_name,
        )

    normal_close = (
        _normal_close_time(
            current_date
        )
    )

    session_open_time = (
        MORNING_OPEN
    )

    session_close_time = (
        normal_close
    )

    phase_boundary = (
        EVENING_START
    )

    if (
        holiday_kind
        == MORNING_CLOSED
    ):
        session_open_time = (
            EVENING_START
        )

    elif (
        holiday_kind
        == EVENING_CLOSED
    ):
        session_close_time = (
            EVENING_START
        )

        phase_boundary = None

    if (
        current_time
        < session_open_time
    ):
        status = (
            "HOLIDAY_MORNING_CLOSED"
            if holiday_kind
            == MORNING_CLOSED
            else "PRE_OPEN"
        )

        return _result(
            status=status,
            session_open=False,
            new_entries_allowed=False,
            position_management_allowed=False,
            close_time=session_close_time,
            note=(
                (
                    f"{holiday_name}: "
                    "morning session closed"
                )
                if holiday_kind
                == MORNING_CLOSED
                else "before session open"
            ),
            holiday_kind=holiday_kind,
            holiday_name=holiday_name,
        )

    if (
        current_time
        >= session_close_time
    ):
        return _result(
            status=(
                "HOLIDAY_EVENING_CLOSED"
                if holiday_kind
                == EVENING_CLOSED
                else "CLOSED"
            ),
            session_open=False,
            new_entries_allowed=False,
            position_management_allowed=False,
            close_time=session_close_time,
            note=(
                (
                    f"{holiday_name}: "
                    "evening session closed"
                )
                if holiday_kind
                == EVENING_CLOSED
                else "after exchange close"
            ),
            holiday_kind=holiday_kind,
            holiday_name=holiday_name,
        )

    close_buffer_start = (
        _minus_minutes(
            session_close_time,
            NEW_ENTRY_BUFFER_MINUTES,
        )
    )

    phase = (
        "MORNING"
        if (
            phase_boundary
            is not None
            and current_time
            < phase_boundary
        )
        else "EVENING"
    )

    if (
        holiday_kind
        == EVENING_CLOSED
    ):
        phase = "MORNING"

    if (
        current_time
        >= close_buffer_start
    ):
        return _result(
            status="CLOSE_BUFFER",
            session_open=True,
            new_entries_allowed=False,
            position_management_allowed=True,
            close_time=session_close_time,
            note=(
                "new entries blocked; "
                "position management remains allowed"
            ),
            phase=phase,
            holiday_kind=holiday_kind,
            holiday_name=holiday_name,
        )

    return _result(
        status="OPEN",
        session_open=True,
        new_entries_allowed=True,
        position_management_allowed=True,
        close_time=session_close_time,
        note=f"{phase} session",
        phase=phase,
        holiday_kind=holiday_kind,
        holiday_name=holiday_name,
    )


def option_expiry_safety(
    option_expiry,
    underlying_futures_expiry,
    now=None,
):
    """Block new entries inside the existing expiry-risk window.

    Existing-position recovery/exit policy is handled separately and is never
    disabled merely because new entries are blocked.
    """

    if now is None:
        now = datetime.now(
            IST
        ).date()

    elif isinstance(
        now,
        datetime,
    ):
        now = _as_ist(
            now
        ).date()

    if isinstance(
        option_expiry,
        str,
    ):
        try:
            option_expiry = (
                datetime.strptime(
                    option_expiry,
                    "%Y-%m-%d",
                )
                .date()
            )

        except Exception:
            return {
                "allow_new_entries":
                    False,
                "days_to_expiry":
                    None,
                "note":
                    "OPTION_EXPIRY_UNPARSEABLE",
            }

    dte = (
        (
            option_expiry
            - now
        ).days
        if option_expiry
        else None
    )

    if dte is None:
        return {
            "allow_new_entries":
                False,
            "days_to_expiry":
                None,
            "note":
                "DTE_UNKNOWN",
        }

    if dte <= 1:
        return {
            "allow_new_entries":
                False,
            "days_to_expiry":
                dte,
            "note":
                f"DTE_{dte}_EXPIRY_RISK",
        }

    if dte <= 2:
        return {
            "allow_new_entries":
                True,
            "days_to_expiry":
                dte,
            "note":
                f"DTE_{dte}_CAUTION",
        }

    return {
        "allow_new_entries":
            True,
        "days_to_expiry":
            dte,
        "note":
            "OK",
    }
