"""Source-listing candidate before exact publication-time enrichment.

SEBI and MCX public listing pages can prove the publication/calendar date
of an item without proving an exact intraday timestamp.

A DATE_ONLY candidate must not be converted directly into
IndianPrimaryNoticeV2 or an AuthoritativeMarketEventV2 by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
)
from urllib.parse import urlparse


LISTING_CANDIDATE_SOURCE_IDS = frozenset(
    {
        "SEBI",
        "MCX",
    }
)

LISTING_TIMESTAMP_PRECISIONS = frozenset(
    {
        "DATE_ONLY",
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

    return value or None


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


def _https_url(
    value: object,
) -> str:
    text = _text(
        value
    )

    if text is None:
        raise ValueError(
            "source_url is required."
        )

    parsed = urlparse(
        text
    )

    if (
        parsed.scheme.lower()
        != "https"
        or not parsed.hostname
    ):
        raise ValueError(
            "source_url must use HTTPS."
        )

    return text


@dataclass(
    frozen=True,
    slots=True,
)
class PrimaryNoticeListingCandidateV2:
    source_id: str
    source_date: date

    title: str
    source_url: str
    observed_at: datetime

    source_item_id: str | None = None
    category: str | None = None

    timestamp_precision: str = (
        "DATE_ONLY"
    )

    schema_version: str = (
        "primary_notice_listing_candidate.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        source_id = (
            self.source_id
            .strip()
            .upper()
            if isinstance(
                self.source_id,
                str,
            )
            else ""
        )

        title = _text(
            self.title
        )

        source_item_id = _text(
            self.source_item_id
        )

        category = _text(
            self.category
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

        if (
            source_id
            not in LISTING_CANDIDATE_SOURCE_IDS
        ):
            raise ValueError(
                "Unsupported listing-candidate source."
            )

        if not isinstance(
            self.source_date,
            date,
        ) or isinstance(
            self.source_date,
            datetime,
        ):
            raise ValueError(
                "source_date must be a date."
            )

        if title is None:
            raise ValueError(
                "title is required."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "observed_at must be timezone-aware."
            )

        source_url = _https_url(
            self.source_url
        )

        if (
            precision
            not in LISTING_TIMESTAMP_PRECISIONS
        ):
            raise ValueError(
                "Unsupported timestamp precision."
            )

        if (
            self.schema_version
            != "primary_notice_listing_candidate.v2"
        ):
            raise ValueError(
                "Invalid listing candidate schema."
            )

        object.__setattr__(
            self,
            "source_id",
            source_id,
        )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "source_item_id",
            source_item_id,
        )

        object.__setattr__(
            self,
            "category",
            category,
        )

        object.__setattr__(
            self,
            "source_url",
            source_url,
        )

        object.__setattr__(
            self,
            "timestamp_precision",
            precision,
        )
