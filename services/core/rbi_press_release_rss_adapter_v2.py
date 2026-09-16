"""RBI official Press Releases RSS adapter.

The RBI RSS feed can publish an exact local wall-clock ``pubDate`` without
publishing a timezone or UTC offset.

A wall-clock value without source timezone provenance must not be converted
directly into ``IndianPrimaryNoticeV2``, whose ``published_at`` contract
requires a timezone-aware datetime.

This module therefore preserves two stages:

1. ``RBIPressReleaseRSSCandidateV2``
   Source-native RSS evidence, including an intraday wall-clock value even
   when its timezone is unspecified.

2. ``promote_rbi_candidate_to_notice``
   Promotion into ``IndianPrimaryNoticeV2`` only when the source timestamp
   itself contains an explicit timezone/offset.

No timezone is inferred from RBI's geography, the machine timezone, fetch
time, or observation time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import (
    urljoin,
    urlparse,
    urlunparse,
)
import xml.etree.ElementTree as ET

from services.contracts.indian_primary_notice_v2 import (
    IndianPrimaryNoticeV2,
)


RBI_PRESS_RELEASE_RSS_URL = (
    "https://rbi.org.in/"
    "pressreleases_rss.xml"
)

RBI_DOMAIN = "rbi.org.in"

RBI_TIMESTAMP_PRECISIONS = frozenset(
    {
        "LOCAL_DATETIME_NO_ZONE",
        "DATETIME_WITH_ZONE",
    }
)

RBI_TIMEZONE_STATUSES = frozenset(
    {
        "SOURCE_UNSPECIFIED",
        "SOURCE_EXPLICIT",
    }
)


def _text(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return (
        value
        or None
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


def _naive(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            datetime,
        )
        and (
            value.tzinfo is None
            or value.utcoffset() is None
        )
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

        self.parts: list[str] = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        value = " ".join(
            data.split()
        )

        if value:
            self.parts.append(
                value
            )


def _visible_text(
    value: str | None,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    if not value.strip():
        return None

    parser = _VisibleTextParser()

    parser.feed(
        value
    )

    parser.close()

    result = " ".join(
        parser.parts
    ).strip()

    return (
        result
        or None
    )


def _normalize_rss_text(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            "RBI RSS payload must be text."
        )

    text = value

    if text.startswith(
        "\ufeff"
    ):
        text = text[1:]

    if text.startswith(
        "ï»¿"
    ):
        try:
            text = (
                text
                .encode(
                    "latin-1"
                )
                .decode(
                    "utf-8-sig"
                )
            )

        except UnicodeError:
            text = text[
                len(
                    "ï»¿"
                ):
            ]

    text = text.lstrip(
        "\ufeff \r\n\t"
    )

    lowered = text.lower()

    if not (
        text.startswith(
            "<?xml"
        )
        or lowered.startswith(
            "<rss"
        )
    ):
        raise ValueError(
            "RBI RSS payload is not an XML/RSS document."
        )

    return text


def _official_rbi_https_url(
    value: str,
) -> str:
    value = _text(
        value
    )

    if value is None:
        raise ValueError(
            "RBI item URL is required."
        )

    url = urljoin(
        RBI_PRESS_RELEASE_RSS_URL,
        value,
    )

    parsed = urlparse(
        url
    )

    host = (
        parsed.hostname
        or ""
    ).lower()

    if not (
        host == RBI_DOMAIN
        or host.endswith(
            "." + RBI_DOMAIN
        )
    ):
        raise ValueError(
            "RBI RSS item URL is outside the authoritative RBI domain."
        )

    if (
        parsed.scheme.lower()
        not in {
            "http",
            "https",
        }
    ):
        raise ValueError(
            "Unsupported RBI RSS item URL scheme."
        )

    # Canonicalize an already-authoritative RBI host to HTTPS.
    secure = parsed._replace(
        scheme="https"
    )

    return urlunparse(
        secure
    )


@dataclass(
    frozen=True,
    slots=True,
)
class RBIPressReleaseRSSCandidateV2:
    title: str
    source_url: str

    source_published_at: datetime
    raw_pub_date: str

    observed_at: datetime

    source_item_id: str | None = None
    detail_text: str | None = None

    timestamp_precision: str = (
        "LOCAL_DATETIME_NO_ZONE"
    )

    timezone_status: str = (
        "SOURCE_UNSPECIFIED"
    )

    schema_version: str = (
        "rbi_press_release_rss_candidate.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        title = _text(
            self.title
        )

        raw_pub_date = _text(
            self.raw_pub_date
        )

        source_item_id = _text(
            self.source_item_id
        )

        detail_text = _text(
            self.detail_text
        )

        precision = (
            self.timestamp_precision
            .strip()
            .upper()
            if isinstance(
                self.timestamp_precision,
                str,
            )
            else ""
        )

        timezone_status = (
            self.timezone_status
            .strip()
            .upper()
            if isinstance(
                self.timezone_status,
                str,
            )
            else ""
        )

        if title is None:
            raise ValueError(
                "title is required."
            )

        if raw_pub_date is None:
            raise ValueError(
                "raw_pub_date is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "observed_at must be timezone-aware."
            )

        source_url = (
            _official_rbi_https_url(
                self.source_url
            )
        )

        if (
            precision
            not in RBI_TIMESTAMP_PRECISIONS
        ):
            raise ValueError(
                "Unsupported RBI timestamp precision."
            )

        if (
            timezone_status
            not in RBI_TIMEZONE_STATUSES
        ):
            raise ValueError(
                "Unsupported RBI timezone status."
            )

        if (
            timezone_status
            == "SOURCE_EXPLICIT"
        ):
            if not _aware(
                self.source_published_at
            ):
                raise ValueError(
                    "SOURCE_EXPLICIT requires timezone-aware source timestamp."
                )

            if (
                precision
                != "DATETIME_WITH_ZONE"
            ):
                raise ValueError(
                    "SOURCE_EXPLICIT requires DATETIME_WITH_ZONE."
                )

        else:
            if not _naive(
                self.source_published_at
            ):
                raise ValueError(
                    "SOURCE_UNSPECIFIED requires timezone-naive source timestamp."
                )

            if (
                precision
                != "LOCAL_DATETIME_NO_ZONE"
            ):
                raise ValueError(
                    "SOURCE_UNSPECIFIED requires LOCAL_DATETIME_NO_ZONE."
                )

        if (
            self.schema_version
            != "rbi_press_release_rss_candidate.v2"
        ):
            raise ValueError(
                "Invalid RBI RSS candidate schema."
            )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "source_url",
            source_url,
        )

        object.__setattr__(
            self,
            "raw_pub_date",
            raw_pub_date,
        )

        object.__setattr__(
            self,
            "source_item_id",
            source_item_id,
        )

        object.__setattr__(
            self,
            "detail_text",
            detail_text,
        )

        object.__setattr__(
            self,
            "timestamp_precision",
            precision,
        )

        object.__setattr__(
            self,
            "timezone_status",
            timezone_status,
        )


def _parse_source_pub_date(
    value: str | None,
) -> tuple[
    datetime,
    str,
    str,
] | None:
    raw = _text(
        value
    )

    if raw is None:
        return None

    try:
        parsed = (
            parsedate_to_datetime(
                raw
            )
        )

    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    if _aware(
        parsed
    ):
        return (
            parsed,
            "DATETIME_WITH_ZONE",
            "SOURCE_EXPLICIT",
        )

    if _naive(
        parsed
    ):
        return (
            parsed,
            "LOCAL_DATETIME_NO_ZONE",
            "SOURCE_UNSPECIFIED",
        )

    return None


def parse_rbi_press_release_rss_candidates(
    xml_text: str,
    *,
    observed_at: datetime,
) -> tuple[
    RBIPressReleaseRSSCandidateV2,
    ...,
]:
    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    normalized = (
        _normalize_rss_text(
            xml_text
        )
    )

    try:
        root = ET.fromstring(
            normalized
        )

    except ET.ParseError as exc:
        raise ValueError(
            "RBI RSS XML is malformed."
        ) from exc

    output: list[
        RBIPressReleaseRSSCandidateV2
    ] = []

    seen: set[
        tuple[
            str,
            str,
        ]
    ] = set()

    for item in root.findall(
        ".//item"
    ):
        title = _text(
            item.findtext(
                "title"
            )
        )

        link = _text(
            item.findtext(
                "link"
            )
        )

        guid = _text(
            item.findtext(
                "guid"
            )
        )

        description = (
            item.findtext(
                "description"
            )
        )

        raw_pub_date = _text(
            item.findtext(
                "pubDate"
            )
        )

        parsed = (
            _parse_source_pub_date(
                raw_pub_date
            )
        )

        if (
            title is None
            or link is None
            or raw_pub_date is None
            or parsed is None
        ):
            continue

        (
            source_published_at,
            precision,
            timezone_status,
        ) = parsed

        source_url = (
            _official_rbi_https_url(
                link
            )
        )

        source_item_id = (
            guid
            or source_url
        )

        key = (
            source_item_id,
            raw_pub_date,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        output.append(
            RBIPressReleaseRSSCandidateV2(
                title=title,
                source_url=source_url,
                source_published_at=(
                    source_published_at
                ),
                raw_pub_date=(
                    raw_pub_date
                ),
                observed_at=(
                    observed_at
                ),
                source_item_id=(
                    source_item_id
                ),
                detail_text=(
                    _visible_text(
                        description
                    )
                ),
                timestamp_precision=(
                    precision
                ),
                timezone_status=(
                    timezone_status
                ),
            )
        )

    return tuple(
        output
    )


def promote_rbi_candidate_to_notice(
    candidate: RBIPressReleaseRSSCandidateV2,
) -> IndianPrimaryNoticeV2 | None:
    if not isinstance(
        candidate,
        RBIPressReleaseRSSCandidateV2,
    ):
        raise ValueError(
            "RBI RSS candidate is required."
        )

    if (
        candidate.timezone_status
        != "SOURCE_EXPLICIT"
        or candidate.timestamp_precision
        != "DATETIME_WITH_ZONE"
        or not _aware(
            candidate.source_published_at
        )
    ):
        return None

    if (
        candidate.source_published_at
        > candidate.observed_at
    ):
        return None

    return IndianPrimaryNoticeV2(
        source_id="RBI",
        notice_kind="PRESS_RELEASE",
        title=(
            candidate.title
        ),
        published_at=(
            candidate.source_published_at
        ),
        source_url=(
            candidate.source_url
        ),
        source_item_id=(
            candidate.source_item_id
        ),
        detail_text=(
            candidate.detail_text
        ),
        affected_symbols=(),
        source_received_at=(
            candidate.observed_at
        ),
        source_disseminated_at=None,
    )


def promote_rbi_candidates_to_notices(
    candidates: tuple[
        RBIPressReleaseRSSCandidateV2,
        ...,
    ],
) -> tuple[
    IndianPrimaryNoticeV2,
    ...,
]:
    output = []

    for candidate in candidates:
        notice = (
            promote_rbi_candidate_to_notice(
                candidate
            )
        )

        if notice is not None:
            output.append(
                notice
            )

    return tuple(
        output
    )


class RBIPressReleaseRSSAdapterV2:
    def __init__(
        self,
        transport,
    ) -> None:
        if transport is None:
            raise ValueError(
                "transport is required."
            )

        self.transport = transport

    def fetch_candidates(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        RBIPressReleaseRSSCandidateV2,
        ...,
    ]:
        xml_text = (
            self.transport
            .fetch_text(
                RBI_PRESS_RELEASE_RSS_URL,
                accepted_content_types=(
                    "text/xml",
                    "application/xml",
                    "application/rss+xml",
                    "text/plain",
                ),
            )
        )

        return (
            parse_rbi_press_release_rss_candidates(
                xml_text,
                observed_at=(
                    observed_at
                ),
            )
        )

    def fetch_notices(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        IndianPrimaryNoticeV2,
        ...,
    ]:
        candidates = (
            self.fetch_candidates(
                observed_at=(
                    observed_at
                ),
            )
        )

        return (
            promote_rbi_candidates_to_notices(
                candidates
            )
        )
