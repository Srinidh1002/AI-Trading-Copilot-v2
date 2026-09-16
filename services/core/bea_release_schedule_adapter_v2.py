"""BEA official release-schedule adapter.

Parses market-relevant GDP and Personal Income and Outlays release
timestamps from the official BEA release schedule.
"""

from __future__ import annotations

from datetime import datetime
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


BEA_RELEASE_SCHEDULE_URL = (
    "https://www.bea.gov/"
    "news/schedule"
)

BEA_LOCAL_TIMEZONE = (
    "America/New_York"
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

_DATE_TIME_RE = re.compile(
    r"^(?P<month>"
    + "|".join(
        month.title()
        for month in _MONTHS
    )
    + r")\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2}):"
    r"(?P<minute>\d{2})\s+"
    r"(?P<ampm>AM|PM)$",
    re.IGNORECASE,
)


class _VisibleTextParser(
    HTMLParser
):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.tokens: list[
            str
        ] = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        value = " ".join(
            data.split()
        )

        if value:
            self.tokens.append(
                value
            )


def _visible_tokens(
    html: str,
) -> list[str]:
    if not isinstance(
        html,
        str,
    ):
        raise ValueError(
            "BEA release schedule payload must be text."
        )

    parser = _VisibleTextParser()
    parser.feed(
        html
    )
    parser.close()

    return parser.tokens


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


def _classify_title(
    title: str,
) -> tuple[
    str,
    str,
] | None:
    normalized = (
        " ".join(
            title
            .lower()
            .split()
        )
    )

    if (
        "personal income and outlays"
        in normalized
    ):
        # Includes the PCE price indexes.
        return (
            "INFLATION_RELEASE",
            "HIGH",
        )

    is_gdp = (
        normalized.startswith(
            "gdp "
        )
        or normalized.startswith(
            "gdp("
        )
        or normalized.startswith(
            "gross domestic product"
        )
        or "gdp (" in normalized
    )

    if is_gdp:
        if (
            "advance estimate"
            in normalized
        ):
            severity = "HIGH"

        else:
            severity = "MEDIUM"

        return (
            "GDP_RELEASE",
            severity,
        )

    return None


def _parse_schedule_datetime(
    token: str,
    *,
    year: int,
) -> datetime | None:
    match = (
        _DATE_TIME_RE
        .fullmatch(
            token.strip()
        )
    )

    if match is None:
        return None

    month = _MONTHS[
        match.group(
            "month"
        ).lower()
    ]

    day = int(
        match.group(
            "day"
        )
    )

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

    ampm = (
        match.group(
            "ampm"
        )
        .upper()
    )

    if (
        hour < 1
        or hour > 12
        or minute < 0
        or minute > 59
    ):
        return None

    if hour == 12:
        hour = 0

    if ampm == "PM":
        hour += 12

    try:
        return datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=ZoneInfo(
                BEA_LOCAL_TIMEZONE
            ),
        )

    except ValueError:
        return None


def parse_bea_release_schedule_html(
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
            "Invalid BEA schedule year."
        )

    source = (
        get_authoritative_event_source(
            "BEA"
        )
    )

    tokens = _visible_tokens(
        html
    )

    events: list[
        AuthoritativeMarketEventV2
    ] = []

    seen: set[
        str
    ] = set()

    for index, token in enumerate(
        tokens
    ):
        scheduled_at = (
            _parse_schedule_datetime(
                token,
                year=year,
            )
        )

        if scheduled_at is None:
            continue

        title = None
        classification = None

        for position in range(
            index + 1,
            min(
                len(tokens),
                index + 14,
            ),
        ):
            candidate = (
                tokens[
                    position
                ]
            )

            if (
                _parse_schedule_datetime(
                    candidate,
                    year=year,
                )
                is not None
            ):
                break

            result = (
                _classify_title(
                    candidate
                )
            )

            if result is not None:
                title = candidate
                classification = result
                break

        if (
            title is None
            or classification is None
        ):
            continue

        event_type, severity = (
            classification
        )

        timestamp_key = (
            scheduled_at.isoformat()
        )

        event_id = _stable_id(
            "BEA",
            title,
            timestamp_key,
        )

        if event_id in seen:
            continue

        seen.add(
            event_id
        )

        group_id = _stable_id(
            "BEA-GROUP",
            event_type,
            title,
            scheduled_at.date().isoformat(),
        )

        events.append(
            AuthoritativeMarketEventV2(
                event_id=event_id,
                event_group_id=group_id,
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
                    BEA_RELEASE_SCHEDULE_URL
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


class BEAReleaseScheduleAdapterV2:
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
        year: int | None = None,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        schedule_year = (
            observed_at.year
            if year is None
            else year
        )

        html = (
            self.transport
            .fetch_text(
                BEA_RELEASE_SCHEDULE_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            parse_bea_release_schedule_html(
                html,
                year=schedule_year,
                observed_at=(
                    observed_at
                ),
            )
        )
