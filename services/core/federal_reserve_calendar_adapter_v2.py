"""Federal Reserve official monthly-calendar adapter.

Parses exact FOMC meeting and minutes timestamps from the Federal Reserve
News & Events monthly calendar.  The adapter is read-only and does not
create trading or hard-block authority by itself.
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


FEDERAL_RESERVE_TIMEZONE = (
    "America/New_York"
)

MONTH_NAMES = {
    1: "january",
    2: "february",
    3: "march",
    4: "april",
    5: "may",
    6: "june",
    7: "july",
    8: "august",
    9: "september",
    10: "october",
    11: "november",
    12: "december",
}

_TIME_RE = re.compile(
    r"^(?P<hour>\d{1,2}):"
    r"(?P<minute>\d{2})\s+"
    r"(?P<ampm>a\.m\.|p\.m\.)$",
    re.IGNORECASE,
)

_DAY_RE = re.compile(
    r"^\d{1,2}$"
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
            "Federal Reserve calendar payload must be text."
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


def federal_reserve_month_url(
    year: int,
    month: int,
) -> str:
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
            "Invalid Federal Reserve calendar year."
        )

    try:
        month_name = MONTH_NAMES[
            month
        ]
    except KeyError as exc:
        raise ValueError(
            "Invalid Federal Reserve calendar month."
        ) from exc

    return (
        "https://www.federalreserve.gov/"
        f"newsevents/{year}-{month_name}.htm"
    )


def _clock_parts(
    value: str,
) -> tuple[
    int,
    int,
] | None:
    match = _TIME_RE.fullmatch(
        value.strip()
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


def _nearest_clock(
    tokens: list[str],
    index: int,
) -> tuple[
    int,
    int,
] | None:
    for position in range(
        index - 1,
        max(
            -1,
            index - 8,
        ),
        -1,
    ):
        clock = _clock_parts(
            tokens[
                position
            ]
        )

        if clock is not None:
            return clock

    return None


def _nearest_day_after(
    tokens: list[str],
    index: int,
) -> int | None:
    for position in range(
        index + 1,
        min(
            len(tokens),
            index + 10,
        ),
    ):
        value = (
            tokens[
                position
            ]
            .strip()
        )

        if _DAY_RE.fullmatch(
            value
        ):
            day = int(
                value
            )

            if 1 <= day <= 31:
                return day

    return None


def parse_federal_reserve_month_calendar_html(
    html: str,
    *,
    year: int,
    month: int,
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

    url = federal_reserve_month_url(
        year,
        month,
    )

    source = (
        get_authoritative_event_source(
            "FEDERAL_RESERVE"
        )
    )

    tokens = _visible_tokens(
        html
    )

    targets = {
        "FOMC Meeting": (
            "CENTRAL_BANK_POLICY",
            "HIGH",
        ),
        "FOMC Minutes": (
            "CENTRAL_BANK_MINUTES",
            "MEDIUM",
        ),
    }

    events: list[
        AuthoritativeMarketEventV2
    ] = []

    seen: set[
        tuple[
            str,
            datetime,
        ]
    ] = set()

    for index, token in enumerate(
        tokens
    ):
        classification = (
            targets.get(
                token
            )
        )

        if classification is None:
            continue

        clock = _nearest_clock(
            tokens,
            index,
        )

        day = _nearest_day_after(
            tokens,
            index,
        )

        if (
            clock is None
            or day is None
        ):
            continue

        hour, minute = clock

        try:
            scheduled_at = datetime(
                year,
                month,
                day,
                hour,
                minute,
                tzinfo=ZoneInfo(
                    FEDERAL_RESERVE_TIMEZONE
                ),
            )
        except ValueError:
            continue

        unique_key = (
            token,
            scheduled_at,
        )

        if unique_key in seen:
            continue

        seen.add(
            unique_key
        )

        event_type, severity = (
            classification
        )

        timestamp_key = (
            scheduled_at.isoformat()
        )

        event_id = _stable_id(
            "FED",
            token,
            timestamp_key,
        )

        group_id = _stable_id(
            "FED-GROUP",
            event_type,
            scheduled_at.date().isoformat(),
        )

        events.append(
            AuthoritativeMarketEventV2(
                event_id=event_id,
                event_group_id=group_id,
                source_id=(
                    source.source_id
                ),
                source_event_id=(
                    f"{year}-"
                    f"{month:02d}-"
                    f"{day:02d}-"
                    f"{event_type}"
                ),
                title=token,
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
                source_url=url,
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


class FederalReserveCalendarAdapterV2:
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

    def fetch_month(
        self,
        *,
        year: int,
        month: int,
        observed_at: datetime,
    ) -> tuple[
        AuthoritativeMarketEventV2,
        ...,
    ]:
        url = federal_reserve_month_url(
            year,
            month,
        )

        html = (
            self.transport
            .fetch_text(
                url,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            parse_federal_reserve_month_calendar_html(
                html,
                year=year,
                month=month,
                observed_at=(
                    observed_at
                ),
            )
        )
