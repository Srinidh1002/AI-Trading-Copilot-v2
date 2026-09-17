"""MoSPI authoritative CPI, IIP and GDP release-schedule adapter.

Calendar dates come from the official MoSPI release calendar. Intraday
release times are attached only where MoSPI publishes an authoritative
release-time policy.

No inferred PLFS release time is created. No trading, broker, strategy,
or certification authority exists in this module.
"""

from __future__ import annotations

from datetime import (
    date,
    datetime,
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


MOSPI_RELEASE_CALENDAR_URL = (
    "https://www.mospi.gov.in/"
    "release-calendar"
)

MOSPI_TIMEZONE = (
    "Asia/Kolkata"
)


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


_MONTH_PATTERN = (
    "Jan(?:uary)?"
    "|Feb(?:ruary)?"
    "|Mar(?:ch)?"
    "|Apr(?:il)?"
    "|May"
    "|Jun(?:e)?"
    "|Jul(?:y)?"
    "|Aug(?:ust)?"
    "|Sep(?:t(?:ember)?)?"
    "|Oct(?:ober)?"
    "|Nov(?:ember)?"
    "|Dec(?:ember)?"
)


_MONTH_CONTEXT_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})"
    r"\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)


_RELEASE_DATE_RE = re.compile(
    rf"(?P<day>\d{{1,2}})"
    r"(?:st|nd|rd|th|[ˢⁿʳᵈᵗʰ]+)?"
    r"\s*"
    rf"(?P<month>{_MONTH_PATTERN})"
    r"(?:\s+(?P<year>\d{4}))?",
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
            "MoSPI release-calendar payload must be text."
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


def _month_number(
    value: str,
) -> int:
    key = (
        value
        .strip()
        .lower()
    )

    try:
        return _MONTHS[
            key
        ]

    except KeyError as exc:
        raise ValueError(
            "Unsupported month."
        ) from exc


def _month_context(
    row: tuple[
        str,
        ...,
    ],
) -> tuple[
    int,
    int,
] | None:
    for cell in row:
        match = (
            _MONTH_CONTEXT_RE
            .search(
                cell
            )
        )

        if match is None:
            continue

        return (
            _month_number(
                match.group(
                    "month"
                )
            ),
            int(
                match.group(
                    "year"
                )
            ),
        )

    return None


def _release_date(
    row: tuple[
        str,
        ...,
    ],
    *,
    default_year: int | None,
) -> date | None:
    for cell in row:
        match = (
            _RELEASE_DATE_RE
            .search(
                cell
            )
        )

        if match is None:
            continue

        year_text = (
            match.group(
                "year"
            )
        )

        year = (
            int(
                year_text
            )
            if year_text is not None
            else default_year
        )

        if year is None:
            continue

        try:
            return date(
                year,
                _month_number(
                    match.group(
                        "month"
                    )
                ),
                int(
                    match.group(
                        "day"
                    )
                ),
            )

        except ValueError:
            continue

    return None


def _classify_title(
    value: str,
) -> tuple[
    str,
    str,
    int,
    int,
] | None:
    normalized = " ".join(
        value.lower().split()
    )

    if (
        "consumer price index"
        in normalized
        and (
            "all india"
            in normalized
            or "(cpi)"
            in normalized
        )
    ):
        # MoSPI CPI dissemination time: 5:30 PM IST.
        return (
            "INFLATION_RELEASE",
            "HIGH",
            17,
            30,
        )

    if (
        "index of industrial production"
        in normalized
        or "(iip)"
        in normalized
    ):
        # MoSPI moved IIP dissemination to 4:00 PM.
        return (
            "INDUSTRIAL_PRODUCTION",
            "MEDIUM",
            16,
            0,
        )

    gdp_marker = (
        "gdp"
        in normalized
        or "gross domestic product"
        in normalized
    )

    estimate_marker = any(
        marker in normalized
        for marker in (
            "estimate",
            "estimates",
            "advance",
            "provisional",
            "revised",
        )
    )

    if (
        gdp_marker
        and estimate_marker
    ):
        # MoSPI GDP dissemination time: 4:00 PM IST.
        return (
            "GDP_RELEASE",
            "HIGH",
            16,
            0,
        )

    # Deliberately skip PLFS and other date-only releases until
    # an authoritative intraday release time is represented.
    return None


def _find_title(
    row: tuple[
        str,
        ...,
    ],
) -> tuple[
    str,
    tuple[
        str,
        str,
        int,
        int,
    ],
] | None:
    for cell in row:
        classification = (
            _classify_title(
                cell
            )
        )

        if classification is not None:
            return (
                cell,
                classification,
            )

    return None


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


def parse_mospi_release_calendar_html(
    html: str,
    *,
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

    source = (
        get_authoritative_event_source(
            "MOSPI"
        )
    )

    current_year: int | None = None

    events: list[
        AuthoritativeMarketEventV2
    ] = []

    seen: set[
        str
    ] = set()

    for row in _table_rows(
        html
    ):
        context = (
            _month_context(
                row
            )
        )

        if context is not None:
            _, current_year = (
                context
            )

        identified = (
            _find_title(
                row
            )
        )

        if identified is None:
            continue

        title, classification = (
            identified
        )

        release_date = (
            _release_date(
                row,
                default_year=(
                    current_year
                ),
            )
        )

        if release_date is None:
            # Never synthesize a calendar date.
            continue

        (
            event_type,
            severity,
            hour,
            minute,
        ) = classification

        scheduled_at = datetime(
            release_date.year,
            release_date.month,
            release_date.day,
            hour,
            minute,
            tzinfo=ZoneInfo(
                MOSPI_TIMEZONE
            ),
        )

        timestamp_key = (
            scheduled_at.isoformat()
        )

        event_id = _stable_id(
            "MOSPI",
            event_type,
            title,
            timestamp_key,
        )

        if event_id in seen:
            continue

        seen.add(
            event_id
        )

        group_id = _stable_id(
            "MOSPI-GROUP",
            event_type,
            release_date.isoformat(),
        )

        events.append(
            AuthoritativeMarketEventV2(
                event_id=event_id,
                event_group_id=(
                    group_id
                ),
                source_id=(
                    source.source_id
                ),
                source_event_id=None,
                title=title,
                event_type=event_type,
                severity=severity,
                jurisdiction=(
                    source.jurisdiction
                ),
                affected_markets=(
                    source.default_markets
                ),
                affected_symbols=(),
                observed_at=(
                    observed_at
                ),
                scheduled=True,
                scheduled_at=(
                    scheduled_at
                ),
                published_at=None,
                effective_at=None,
                source_url=(
                    MOSPI_RELEASE_CALENDAR_URL
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


class MoSPIReleaseScheduleAdapterV2:
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

    def fetch_events(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        html = (
            self.transport
            .fetch_text(
                MOSPI_RELEASE_CALENDAR_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            parse_mospi_release_calendar_html(
                html,
                observed_at=(
                    observed_at
                ),
            )
        )
