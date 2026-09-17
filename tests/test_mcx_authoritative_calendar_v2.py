"""MCX authoritative-calendar safety tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

from mcx.mcx_calendar import (
    IST,
    get_session,
    option_expiry_safety,
)
from mcx.mcx_holidays import (
    AUTHORITATIVE_CALENDAR_YEARS,
    EVENING_CLOSED,
    FULL,
    MORNING_CLOSED,
    count,
    holiday_record,
    validate_authority,
)


def dt(
    year,
    month,
    day,
    hour,
    minute=0,
):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=IST,
    )


def test_authoritative_year_is_exact_2026():
    assert (
        AUTHORITATIVE_CALENDAR_YEARS
        == frozenset({
            2026,
        })
    )


def test_official_2026_holiday_count_is_16():
    assert count() == 16
    assert validate_authority() is True


def test_key_holiday_types_match_official_schedule():
    jan1 = holiday_record(
        2026,
        1,
        1,
    )

    jan26 = holiday_record(
        2026,
        1,
        26,
    )

    sep14 = holiday_record(
        2026,
        9,
        14,
    )

    oct2 = holiday_record(
        2026,
        10,
        2,
    )

    assert (
        jan1["kind"]
        == EVENING_CLOSED
    )

    assert (
        jan26["kind"]
        == FULL
    )

    assert (
        sep14["kind"]
        == MORNING_CLOSED
    )

    assert (
        oct2["kind"]
        == FULL
    )


def test_today_sep18_is_normal_open_day_at_10_ist():
    s = get_session(
        dt(
            2026,
            9,
            18,
            10,
            0,
        )
    )

    assert s["status"] == "OPEN"
    assert s["session_open"] is True
    assert (
        s["new_entries_allowed"]
        is True
    )

    assert (
        s[
            "position_management_allowed"
        ]
        is True
    )

    assert (
        s[
            "calendar_authoritative"
        ]
        is True
    )


def test_ganesh_morning_closed_evening_open():
    morning = get_session(
        dt(
            2026,
            9,
            14,
            10,
            0,
        )
    )

    evening = get_session(
        dt(
            2026,
            9,
            14,
            18,
            0,
        )
    )

    assert (
        morning["status"]
        == "HOLIDAY_MORNING_CLOSED"
    )

    assert (
        morning[
            "new_entries_allowed"
        ]
        is False
    )

    assert evening["status"] == "OPEN"
    assert (
        evening[
            "new_entries_allowed"
        ]
        is True
    )

    assert evening["phase"] == "EVENING"


def test_new_year_morning_open_evening_closed():
    morning = get_session(
        dt(
            2026,
            1,
            1,
            10,
            0,
        )
    )

    close_buffer = get_session(
        dt(
            2026,
            1,
            1,
            16,
            50,
        )
    )

    closed = get_session(
        dt(
            2026,
            1,
            1,
            17,
            0,
        )
    )

    assert morning["status"] == "OPEN"

    assert (
        close_buffer["status"]
        == "CLOSE_BUFFER"
    )

    assert (
        close_buffer[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        close_buffer[
            "position_management_allowed"
        ]
        is True
    )

    assert (
        closed["status"]
        == "HOLIDAY_EVENING_CLOSED"
    )

    assert (
        closed["session_open"]
        is False
    )


def test_full_holiday_is_exchange_closed():
    s = get_session(
        dt(
            2026,
            1,
            26,
            10,
            0,
        )
    )

    assert (
        s["status"]
        == "HOLIDAY_FULL_CLOSED"
    )

    assert (
        s["new_entries_allowed"]
        is False
    )

    assert (
        s[
            "position_management_allowed"
        ]
        is False
    )


def test_close_buffer_blocks_entry_but_keeps_management():
    # Sep 18 is during US DST:
    # close 23:30, entry buffer begins 23:15.
    s = get_session(
        dt(
            2026,
            9,
            18,
            23,
            20,
        )
    )

    assert s["status"] == "CLOSE_BUFFER"

    assert (
        s["session_open"]
        is True
    )

    assert (
        s[
            "new_entries_allowed"
        ]
        is False
    )

    assert (
        s[
            "position_management_allowed"
        ]
        is True
    )


def test_after_actual_close_management_is_closed():
    s = get_session(
        dt(
            2026,
            9,
            18,
            23,
            31,
        )
    )

    assert s["status"] == "CLOSED"
    assert s["session_open"] is False

    assert (
        s[
            "position_management_allowed"
        ]
        is False
    )


def test_non_dst_close_buffer_uses_2355_close():
    # Dec 18, 2026 is not a holiday and US DST has ended.
    open_late = get_session(
        dt(
            2026,
            12,
            18,
            23,
            35,
        )
    )

    close_buffer = get_session(
        dt(
            2026,
            12,
            18,
            23,
            45,
        )
    )

    assert (
        open_late["status"]
        == "OPEN"
    )

    assert (
        close_buffer["status"]
        == "CLOSE_BUFFER"
    )


def test_weekend_closed():
    s = get_session(
        dt(
            2026,
            9,
            19,
            10,
            0,
        )
    )

    assert s["status"] == "WEEKEND"
    assert s["tradable"] is False


def test_unknown_year_fails_closed():
    s = get_session(
        dt(
            2027,
            1,
            4,
            10,
            0,
        )
    )

    assert (
        s["status"]
        == "CALENDAR_UNKNOWN"
    )

    assert (
        s[
            "calendar_authoritative"
        ]
        is False
    )

    assert (
        s[
            "new_entries_allowed"
        ]
        is False
    )


def test_naive_datetime_is_interpreted_as_ist_for_backward_compatibility():
    naive = datetime(
        2026,
        9,
        18,
        10,
        0,
    )

    s = get_session(
        naive
    )

    assert s["status"] == "OPEN"


def test_expiry_safety_still_blocks_dte_one():
    result = option_expiry_safety(
        "2026-09-19",
        "2026-09-30",
        now=dt(
            2026,
            9,
            18,
            10,
            0,
        ),
    )

    assert (
        result[
            "allow_new_entries"
        ]
        is False
    )

    assert (
        result[
            "days_to_expiry"
        ]
        == 1
    )
