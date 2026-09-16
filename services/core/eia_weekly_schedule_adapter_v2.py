"""EIA authoritative weekly petroleum and natural-gas schedule adapter.

Builds concrete timezone-aware weekly release events from the official EIA
standard cadence plus explicit holiday-release overrides.

This module is read-only market intelligence.  It has no trading, broker,
strategy-weight, certification-counter, or order authority.
"""

from __future__ import annotations

from datetime import (
    date,
    datetime,
    timedelta,
)
import hashlib
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

from services.contracts.authoritative_event_v2 import (
    AuthoritativeMarketEventV2,
)
from services.core.authoritative_event_source_catalog_v2 import (
    get_authoritative_event_source,
)


EIA_TIMEZONE = "America/New_York"

EIA_PETROLEUM_SCHEDULE_URL = (
    "https://www.eia.gov/"
    "petroleum/supply/weekly/schedule.php"
)

EIA_NATURAL_GAS_SCHEDULE_URL = (
    "https://ir.eia.gov/"
    "ngs/schedule.html"
)


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


_DATE_RE = re.compile(
    r"(?P<month>"
    + "|".join(
        name.title()
        for name in _MONTHS
    )
    + r")\s+"
    r"(?P<day>\d{1,2}),\s+"
    r"(?P<year>\d{4})",
    re.IGNORECASE,
)


_TIME_RE = re.compile(
    r"(?P<hour>\d{1,2}):"
    r"(?P<minute>\d{2})\s*"
    r"(?P<ampm>a\.m\.|p\.m\.)",
    re.IGNORECASE,
)


class _TableParser(
    HTMLParser
):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.rows: list[
            list[str]
        ] = []

        self._row: list[
            str
        ] | None = None

        self._cell: list[
            str
        ] | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs,
    ) -> None:
        del attrs

        name = tag.lower()

        if name == "tr":
            self._row = []

        elif (
            name in {
                "td",
                "th",
            }
            and self._row is not None
        ):
            self._cell = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if self._cell is not None:
            self._cell.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        name = tag.lower()

        if (
            name in {
                "td",
                "th",
            }
            and self._cell is not None
            and self._row is not None
        ):
            value = " ".join(
                "".join(
                    self._cell
                ).split()
            )

            self._row.append(
                value
            )

            self._cell = None

        elif (
            name == "tr"
            and self._row is not None
        ):
            if self._row:
                self.rows.append(
                    self._row
                )

            self._row = None
            self._cell = None


def _table_rows(
    html: str,
) -> tuple[
    tuple[str, ...],
    ...,
]:
    if not isinstance(
        html,
        str,
    ):
        raise ValueError(
            "EIA schedule payload must be text."
        )

    parser = _TableParser()

    parser.feed(
        html
    )

    parser.close()

    return tuple(
        tuple(
            row
        )
        for row in parser.rows
    )


def _aware(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            datetime,
        )
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _parse_date(
    value: str,
) -> date | None:
    match = _DATE_RE.search(
        value
    )

    if match is None:
        return None

    month = _MONTHS[
        match.group(
            "month"
        ).lower()
    ]

    try:
        return date(
            int(
                match.group(
                    "year"
                )
            ),
            month,
            int(
                match.group(
                    "day"
                )
            ),
        )

    except ValueError:
        return None


def _parse_time(
    value: str,
) -> tuple[
    int,
    int,
] | None:
    match = _TIME_RE.search(
        value
    )

    if match is None:
        return None

    hour = int(
        match.group(
            "hour"
        )
    )

    minute = int(
        match.group(
            "minute"
        )
    )

    if (
        hour < 1
        or hour > 12
        or minute < 0
        or minute > 59
    ):
        return None

    ampm = (
        match.group(
            "ampm"
        )
        .lower()
    )

    if hour == 12:
        hour = 0

    if ampm.startswith(
        "p"
    ):
        hour += 12

    return (
        hour,
        minute,
    )


def _weekly_dates(
    year: int,
    weekday: int,
) -> tuple[
    date,
    ...,
]:
    if (
        not isinstance(
            year,
            int,
        )
        or isinstance(
            year,
            bool,
        )
        or year < 2000
    ):
        raise ValueError(
            "Invalid EIA schedule year."
        )

    if weekday not in range(
        7
    ):
        raise ValueError(
            "Invalid weekday."
        )

    current = date(
        year,
        1,
        1,
    )

    offset = (
        weekday
        - current.weekday()
    ) % 7

    current += timedelta(
        days=offset
    )

    values: list[
        date
    ] = []

    while current.year == year:
        values.append(
            current
        )

        current += timedelta(
            days=7
        )

    return tuple(
        values
    )


def _at_eastern(
    release_date: date,
    hour: int,
    minute: int,
) -> datetime:
    return datetime(
        release_date.year,
        release_date.month,
        release_date.day,
        hour,
        minute,
        tzinfo=ZoneInfo(
            EIA_TIMEZONE
        ),
    )


def _stable_id(
    prefix: str,
    *parts: str,
) -> str:
    digest = (
        hashlib.sha256(
            "|".join(
                parts
            ).encode(
                "utf-8"
            )
        )
        .hexdigest()[:20]
    )

    return (
        f"{prefix}:{digest}"
    )


def _event(
    *,
    event_kind: str,
    release_at: datetime,
    observed_at: datetime,
) -> AuthoritativeMarketEventV2:
    source = (
        get_authoritative_event_source(
            "EIA"
        )
    )

    if event_kind == "PETROLEUM":
        title = (
            "EIA Weekly Petroleum "
            "Status Report"
        )

        event_type = (
            "COMMODITY_INVENTORY"
        )

        markets = (
            "CRUDEOILM",
        )

        source_url = (
            EIA_PETROLEUM_SCHEDULE_URL
        )

        prefix = "EIA-WPSR"

    elif event_kind == "NATURAL_GAS":
        title = (
            "EIA Weekly Natural Gas "
            "Storage Report"
        )

        event_type = (
            "NATGAS_STORAGE"
        )

        markets = (
            "NATGASMINI",
        )

        source_url = (
            EIA_NATURAL_GAS_SCHEDULE_URL
        )

        prefix = "EIA-WNGSR"

    else:
        raise ValueError(
            "Unsupported EIA weekly event kind."
        )

    timestamp_key = (
        release_at.isoformat()
    )

    event_id = _stable_id(
        prefix,
        timestamp_key,
    )

    group_id = _stable_id(
        prefix + "-GROUP",
        release_at.date().isoformat(),
    )

    return (
        AuthoritativeMarketEventV2(
            event_id=event_id,
            event_group_id=group_id,
            source_id=(
                source.source_id
            ),
            source_event_id=None,
            title=title,
            event_type=event_type,
            severity="HIGH",
            jurisdiction=(
                source.jurisdiction
            ),
            affected_markets=markets,
            affected_symbols=(),
            observed_at=observed_at,
            scheduled=True,
            scheduled_at=release_at,
            published_at=None,
            effective_at=None,
            source_url=source_url,
        )
    )


def _petroleum_overrides(
    html: str,
    *,
    year: int,
) -> dict[
    date,
    tuple[
        date,
        int,
        int,
    ],
]:
    """Map standard Wednesday date to official alternate release."""

    result: dict[
        date,
        tuple[
            date,
            int,
            int,
        ],
    ] = {}

    for row in _table_rows(
        html
    ):
        dates = [
            parsed
            for parsed in (
                _parse_date(
                    cell
                )
                for cell in row
            )
            if parsed is not None
        ]

        times = [
            parsed
            for parsed in (
                _parse_time(
                    cell
                )
                for cell in row
            )
            if parsed is not None
        ]

        if (
            len(
                dates
            ) < 2
            or not times
        ):
            continue

        week_ending = (
            dates[0]
        )

        alternate = (
            dates[1]
        )

        if alternate.year != year:
            continue

        # WPSR standard release is the Wednesday
        # five days after the Friday data-week end.
        standard = (
            week_ending
            + timedelta(
                days=5
            )
        )

        hour, minute = (
            times[0]
        )

        if standard in result:
            raise ValueError(
                "Duplicate EIA petroleum holiday override."
            )

        result[
            standard
        ] = (
            alternate,
            hour,
            minute,
        )

    return result


def _natural_gas_overrides(
    html: str,
    *,
    year: int,
    standard_dates: tuple[
        date,
        ...,
    ],
) -> dict[
    date,
    tuple[
        date,
        int,
        int,
    ],
]:
    """Map standard Thursday date to official alternate release.

    Natural-gas exception rows do not provide the underlying data-week date.
    We therefore accept an override only when exactly one standard Thursday
    exists in the same ISO week.  Any ambiguous future format fails closed.
    """

    result: dict[
        date,
        tuple[
            date,
            int,
            int,
        ],
    ] = {}

    for row in _table_rows(
        html
    ):
        dates = [
            parsed
            for parsed in (
                _parse_date(
                    cell
                )
                for cell in row
            )
            if parsed is not None
        ]

        times = [
            parsed
            for parsed in (
                _parse_time(
                    cell
                )
                for cell in row
            )
            if parsed is not None
        ]

        if (
            not dates
            or not times
        ):
            continue

        alternate = (
            dates[0]
        )

        if alternate.year != year:
            continue

        iso_year, iso_week, _ = (
            alternate.isocalendar()
        )

        candidates = [
            value
            for value in standard_dates
            if (
                value.isocalendar().year
                == iso_year
                and value.isocalendar().week
                == iso_week
            )
        ]

        if len(
            candidates
        ) != 1:
            raise ValueError(
                "Natural gas holiday override "
                "cannot be resolved conservatively."
            )

        standard = (
            candidates[0]
        )

        hour, minute = (
            times[0]
        )

        if standard in result:
            raise ValueError(
                "Duplicate EIA natural-gas holiday override."
            )

        result[
            standard
        ] = (
            alternate,
            hour,
            minute,
        )

    return result


def build_eia_petroleum_schedule(
    html: str,
    *,
    year: int,
    observed_at: datetime,
) -> tuple[
    AuthoritativeMarketEventV2,
    ...,
]:
    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    # Wednesday.
    standard_dates = (
        _weekly_dates(
            year,
            2,
        )
    )

    overrides = (
        _petroleum_overrides(
            html,
            year=year,
        )
    )

    release_times: dict[
        date,
        datetime,
    ] = {
        value: _at_eastern(
            value,
            10,
            30,
        )
        for value
        in standard_dates
    }

    for (
        standard,
        (
            alternate,
            hour,
            minute,
        ),
    ) in overrides.items():
        if standard not in release_times:
            raise ValueError(
                "Petroleum holiday override "
                "does not match a standard release."
            )

        del release_times[
            standard
        ]

        if alternate in release_times:
            raise ValueError(
                "Petroleum holiday override "
                "collides with another release."
            )

        release_times[
            alternate
        ] = _at_eastern(
            alternate,
            hour,
            minute,
        )

    return tuple(
        _event(
            event_kind="PETROLEUM",
            release_at=value,
            observed_at=observed_at,
        )
        for value
        in sorted(
            release_times.values()
        )
    )


def build_eia_natural_gas_schedule(
    html: str,
    *,
    year: int,
    observed_at: datetime,
) -> tuple[
    AuthoritativeMarketEventV2,
    ...,
]:
    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    # Thursday.
    standard_dates = (
        _weekly_dates(
            year,
            3,
        )
    )

    overrides = (
        _natural_gas_overrides(
            html,
            year=year,
            standard_dates=(
                standard_dates
            ),
        )
    )

    release_times: dict[
        date,
        datetime,
    ] = {
        value: _at_eastern(
            value,
            10,
            30,
        )
        for value
        in standard_dates
    }

    for (
        standard,
        (
            alternate,
            hour,
            minute,
        ),
    ) in overrides.items():
        if standard not in release_times:
            raise ValueError(
                "Natural-gas holiday override "
                "does not match a standard release."
            )

        del release_times[
            standard
        ]

        if alternate in release_times:
            raise ValueError(
                "Natural-gas holiday override "
                "collides with another release."
            )

        release_times[
            alternate
        ] = _at_eastern(
            alternate,
            hour,
            minute,
        )

    return tuple(
        _event(
            event_kind="NATURAL_GAS",
            release_at=value,
            observed_at=observed_at,
        )
        for value
        in sorted(
            release_times.values()
        )
    )


class EIAWeeklyScheduleAdapterV2:
    def __init__(
        self,
        transport,
    ) -> None:
        if transport is None:
            raise ValueError(
                "transport is required."
            )

        self.transport = (
            transport
        )

    def fetch_petroleum(
        self,
        *,
        year: int,
        observed_at: datetime,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        html = (
            self.transport
            .fetch_text(
                EIA_PETROLEUM_SCHEDULE_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            build_eia_petroleum_schedule(
                html,
                year=year,
                observed_at=(
                    observed_at
                ),
            )
        )

    def fetch_natural_gas(
        self,
        *,
        year: int,
        observed_at: datetime,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        html = (
            self.transport
            .fetch_text(
                EIA_NATURAL_GAS_SCHEDULE_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            build_eia_natural_gas_schedule(
                html,
                year=year,
                observed_at=(
                    observed_at
                ),
            )
        )

    def fetch_all(
        self,
        *,
        year: int,
        observed_at: datetime,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        events = (
            self.fetch_petroleum(
                year=year,
                observed_at=(
                    observed_at
                ),
            )
            + self.fetch_natural_gas(
                year=year,
                observed_at=(
                    observed_at
                ),
            )
        )

        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.scheduled_at,
                    event.event_id,
                ),
            )
        )
