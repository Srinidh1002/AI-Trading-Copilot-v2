"""BLS official release-calendar adapter.

The BLS iCalendar feed is read-only official schedule evidence.
The adapter does not score markets, block entries, or submit orders.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
import hashlib
import re
from zoneinfo import ZoneInfo

from services.contracts.authoritative_event_v2 import (
    AuthoritativeMarketEventV2,
)
from services.core.authoritative_event_source_catalog_v2 import (
    get_authoritative_event_source,
)


BLS_ICS_URL = (
    "https://www.bls.gov/"
    "schedule/news_release/bls.ics"
)

BLS_LOCAL_TIMEZONE = (
    "America/New_York"
)


_EVENT_RULES = (
    (
        "consumer price index",
        "INFLATION_RELEASE",
        "HIGH",
    ),
    (
        "producer price index",
        "INFLATION_RELEASE",
        "MEDIUM",
    ),
    (
        "import and export price",
        "INFLATION_RELEASE",
        "MEDIUM",
    ),
    (
        "real earnings",
        "INFLATION_RELEASE",
        "LOW",
    ),
    (
        "employment situation",
        "EMPLOYMENT_RELEASE",
        "HIGH",
    ),
    (
        "job openings and labor turnover",
        "EMPLOYMENT_RELEASE",
        "MEDIUM",
    ),
    (
        "employment cost index",
        "EMPLOYMENT_RELEASE",
        "MEDIUM",
    ),
    (
        "employer costs for employee compensation",
        "EMPLOYMENT_RELEASE",
        "MEDIUM",
    ),
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


def _unescape_ics(
    value: str,
) -> str:
    return (
        value
        .replace(
            "\\n",
            " ",
        )
        .replace(
            "\\N",
            " ",
        )
        .replace(
            "\\,",
            ",",
        )
        .replace(
            "\\;",
            ";",
        )
        .replace(
            "\\\\",
            "\\",
        )
        .strip()
    )


def _unfold_ics_lines(
    text: str,
) -> list[str]:
    normalized = (
        text
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    output: list[str] = []

    for line in normalized.split(
        "\n"
    ):
        if (
            line.startswith(
                " "
            )
            or line.startswith(
                "\t"
            )
        ):
            if not output:
                raise ValueError(
                    "Invalid folded ICS line."
                )

            output[-1] += (
                line[1:]
            )

        else:
            output.append(
                line
            )

    return output


def _parse_property(
    line: str,
) -> tuple[
    str,
    dict[str, str],
    str,
]:
    if ":" not in line:
        raise ValueError(
            "Invalid ICS property."
        )

    left, value = line.split(
        ":",
        1,
    )

    parts = left.split(
        ";"
    )

    name = (
        parts[0]
        .strip()
        .upper()
    )

    params: dict[
        str,
        str,
    ] = {}

    for item in parts[
        1:
    ]:
        if "=" not in item:
            continue

        key, param_value = (
            item.split(
                "=",
                1,
            )
        )

        params[
            key.strip().upper()
        ] = (
            param_value
            .strip()
            .strip(
                '"'
            )
        )

    return (
        name,
        params,
        value.strip(),
    )


def _parse_dtstart(
    value: str,
    params: dict[
        str,
        str,
    ],
) -> datetime | None:
    if (
        params.get(
            "VALUE",
            "",
        ).upper()
        == "DATE"
    ):
        return None

    if re.fullmatch(
        r"\d{8}",
        value,
    ):
        # Date-only events, such as holidays,
        # are not timed economic releases.
        return None

    if value.endswith(
        "Z"
    ):
        parsed = datetime.strptime(
            value,
            "%Y%m%dT%H%M%SZ",
        )

        return parsed.replace(
            tzinfo=timezone.utc
        )

    parsed = datetime.strptime(
        value,
        "%Y%m%dT%H%M%S",
    )

    tzid = params.get(
        "TZID",
        BLS_LOCAL_TIMEZONE,
    )

    return parsed.replace(
        tzinfo=ZoneInfo(
            tzid
        )
    )


def _classify_summary(
    summary: str,
) -> tuple[
    str,
    str,
] | None:
    normalized = (
        " ".join(
            summary
            .lower()
            .split()
        )
    )

    for (
        marker,
        event_type,
        severity,
    ) in _EVENT_RULES:
        if marker in normalized:
            return (
                event_type,
                severity,
            )

    return None


def _stable_id(
    prefix: str,
    *parts: str,
) -> str:
    raw = "|".join(
        parts
    ).encode(
        "utf-8"
    )

    digest = (
        hashlib.sha256(
            raw
        )
        .hexdigest()[
            :20
        ]
    )

    return (
        f"{prefix}:{digest}"
    )


def parse_bls_calendar_ics(
    text: str,
    *,
    observed_at: datetime,
) -> tuple[
    AuthoritativeMarketEventV2,
    ...,
]:
    if not isinstance(
        text,
        str,
    ):
        raise ValueError(
            "BLS ICS payload must be text."
        )

    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    source = (
        get_authoritative_event_source(
            "BLS"
        )
    )

    rows: list[
        dict[str, object]
    ] = []

    current: dict[
        str,
        object,
    ] | None = None

    for line in _unfold_ics_lines(
        text
    ):
        if line == "BEGIN:VEVENT":
            if current is not None:
                raise ValueError(
                    "Nested VEVENT is invalid."
                )

            current = {}

            continue

        if line == "END:VEVENT":
            if current is None:
                raise ValueError(
                    "END:VEVENT without BEGIN:VEVENT."
                )

            rows.append(
                current
            )

            current = None

            continue

        if current is None:
            continue

        if not line.strip():
            continue

        name, params, value = (
            _parse_property(
                line
            )
        )

        if name == "DTSTART":
            current[
                "dtstart"
            ] = (
                _parse_dtstart(
                    value,
                    params,
                )
            )

        elif name in {
            "SUMMARY",
            "UID",
            "URL",
        }:
            current[
                name.lower()
            ] = (
                _unescape_ics(
                    value
                )
            )

    if current is not None:
        raise ValueError(
            "Unclosed VEVENT."
        )

    events: list[
        AuthoritativeMarketEventV2
    ] = []

    seen: set[
        str
    ] = set()

    for row in rows:
        summary = row.get(
            "summary"
        )

        scheduled_at = row.get(
            "dtstart"
        )

        if (
            not isinstance(
                summary,
                str,
            )
            or not isinstance(
                scheduled_at,
                datetime,
            )
        ):
            continue

        classification = (
            _classify_summary(
                summary
            )
        )

        if classification is None:
            continue

        (
            event_type,
            severity,
        ) = classification

        source_event_id = (
            row.get(
                "uid"
            )
            if isinstance(
                row.get(
                    "uid"
                ),
                str,
            )
            else None
        )

        timestamp_key = (
            scheduled_at
            .astimezone(
                timezone.utc
            )
            .isoformat()
        )

        event_id = _stable_id(
            "BLS",
            source_event_id or "",
            summary,
            timestamp_key,
        )

        if event_id in seen:
            continue

        seen.add(
            event_id
        )

        event_group_id = (
            _stable_id(
                "BLS-GROUP",
                event_type,
                summary,
                scheduled_at.date().isoformat(),
            )
        )

        events.append(
            AuthoritativeMarketEventV2(
                event_id=event_id,
                event_group_id=(
                    event_group_id
                ),
                source_id=(
                    source.source_id
                ),
                source_event_id=(
                    source_event_id
                ),
                title=summary,
                event_type=(
                    event_type
                ),
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
                    BLS_ICS_URL
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


class BLSCalendarAdapterV2:
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
        payload = (
            self.transport
            .fetch_text(
                BLS_ICS_URL,
                accepted_content_types=(
                    "text/calendar",
                    "text/plain",
                    "application/octet-stream",
                ),
            )
        )

        return parse_bls_calendar_ics(
            payload,
            observed_at=(
                observed_at
            ),
        )
