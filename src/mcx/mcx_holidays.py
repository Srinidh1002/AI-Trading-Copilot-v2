"""Authoritative MCX trading-holiday calendar for 2026.

Source authority:
MCX Trading Holidays — calendar year 2026.

Session semantics:
- FULL:
    morning closed, evening closed
- MORNING_CLOSED:
    09:00-17:00 closed; evening session open
- EVENING_CLOSED:
    morning session open; session ends at 17:00

Only years explicitly listed in AUTHORITATIVE_CALENDAR_YEARS are considered
calendar-authoritative. Unknown years fail closed for NEW entries.

Muhurat trading is not inferred from the ordinary Sunday/weekend calendar.
It requires a separately verified exchange timing before being enabled.
"""

from __future__ import annotations


FULL = "FULL"
MORNING_CLOSED = "MORNING_CLOSED"
EVENING_CLOSED = "EVENING_CLOSED"


AUTHORITATIVE_CALENDAR_YEARS = frozenset({
    2026,
})


# Official MCX 2026 trading-holiday schedule.
#
# tuple:
# (year, month, day, exchange_name, closure_kind)
MCX_HOLIDAYS_2026 = (
    (
        2026, 1, 1,
        "NEW_YEAR_DAY",
        EVENING_CLOSED,
    ),
    (
        2026, 1, 26,
        "REPUBLIC_DAY",
        FULL,
    ),
    (
        2026, 3, 3,
        "HOLI",
        MORNING_CLOSED,
    ),
    (
        2026, 3, 26,
        "SHRI_RAM_NAVMI",
        MORNING_CLOSED,
    ),
    (
        2026, 3, 31,
        "SHRI_MAHAVIR_JAYANTI",
        MORNING_CLOSED,
    ),
    (
        2026, 4, 3,
        "GOOD_FRIDAY",
        FULL,
    ),
    (
        2026, 4, 14,
        "DR_BABASAHEB_AMBEDKAR_JAYANTI",
        MORNING_CLOSED,
    ),
    (
        2026, 5, 1,
        "MAHARASHTRA_DAY",
        MORNING_CLOSED,
    ),
    (
        2026, 5, 28,
        "BAKRI_ID",
        MORNING_CLOSED,
    ),
    (
        2026, 6, 26,
        "MOHARRAM",
        MORNING_CLOSED,
    ),
    (
        2026, 9, 14,
        "GANESH_CHATURTHI",
        MORNING_CLOSED,
    ),
    (
        2026, 10, 2,
        "MAHATMA_GANDHI_JAYANTI",
        FULL,
    ),
    (
        2026, 10, 20,
        "DASSERA",
        MORNING_CLOSED,
    ),
    (
        2026, 11, 10,
        "DIWALI_BALIPRATIPADA",
        MORNING_CLOSED,
    ),
    (
        2026, 11, 24,
        "GURU_NANAK_JAYANTI",
        MORNING_CLOSED,
    ),
    (
        2026, 12, 25,
        "CHRISTMAS",
        FULL,
    ),
)


_HOLIDAY_INDEX = {
    (year, month, day): {
        "year": year,
        "month": month,
        "day": day,
        "name": name,
        "kind": kind,
    }
    for (
        year,
        month,
        day,
        name,
        kind,
    )
    in MCX_HOLIDAYS_2026
}


def is_calendar_year_authoritative(
    year,
):
    try:
        year = int(year)
    except (
        TypeError,
        ValueError,
    ):
        return False

    return (
        year
        in AUTHORITATIVE_CALENDAR_YEARS
    )


def holiday_record(
    year,
    month,
    day,
):
    try:
        key = (
            int(year),
            int(month),
            int(day),
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    return _HOLIDAY_INDEX.get(
        key
    )


def is_holiday(
    year,
    month,
    day,
):
    """Backward-compatible tuple API.

    Returns:
        (kind, name)
        or
        (None, None)
    """

    record = holiday_record(
        year,
        month,
        day,
    )

    if record is None:
        return None, None

    return (
        record["kind"],
        record["name"],
    )


def count():
    return len(
        MCX_HOLIDAYS_2026
    )


def validate_authority():
    if count() != 16:
        return False

    keys = [
        (
            y,
            m,
            d,
        )
        for (
            y,
            m,
            d,
            _name,
            _kind,
        )
        in MCX_HOLIDAYS_2026
    ]

    if (
        len(keys)
        != len(set(keys))
    ):
        return False

    valid_kinds = {
        FULL,
        MORNING_CLOSED,
        EVENING_CLOSED,
    }

    return all(
        kind in valid_kinds
        for (
            _y,
            _m,
            _d,
            _name,
            kind,
        )
        in MCX_HOLIDAYS_2026
    )
