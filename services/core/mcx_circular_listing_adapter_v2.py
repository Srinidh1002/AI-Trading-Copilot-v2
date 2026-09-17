"""MCX official circular-listing adapter.

The MCX circular table exposes date, category, title and circular number,
but not a proven exact publication time. Therefore this adapter emits
DATE_ONLY candidates only.
"""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import (
    urljoin,
    urlparse,
)

from services.contracts.primary_notice_listing_candidate_v2 import (
    PrimaryNoticeListingCandidateV2,
)


MCX_CIRCULAR_LISTING_URL = (
    "https://www.mcxindia.com/"
    "circulars/all-circulars"
)

MCX_DOMAIN = (
    "mcxindia.com"
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

        self.rows = []

        self._row = None
        self._cell = None
        self._href = None

    def handle_starttag(
        self,
        tag,
        attrs,
    ) -> None:
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
            self._href = None

        elif (
            name == "a"
            and self._cell is not None
        ):
            values = dict(
                attrs
            )

            href = values.get(
                "href"
            )

            if isinstance(
                href,
                str,
            ):
                self._href = (
                    href.strip()
                    or None
                )

    def handle_data(
        self,
        data,
    ) -> None:
        if self._cell is not None:
            self._cell.append(
                data
            )

    def handle_endtag(
        self,
        tag,
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
                (
                    value,
                    self._href,
                )
            )

            self._cell = None
            self._href = None

        elif (
            name == "tr"
            and self._row is not None
        ):
            if self._row:
                self.rows.append(
                    self._row
                )

            self._row = None


def _official_url(
    href: str | None,
) -> str | None:
    if not href:
        return None

    url = urljoin(
        MCX_CIRCULAR_LISTING_URL,
        href,
    )

    parsed = urlparse(
        url
    )

    host = (
        parsed.hostname
        or ""
    ).lower()

    if not (
        parsed.scheme.lower()
        == "https"
        and (
            host == MCX_DOMAIN
            or host.endswith(
                "." + MCX_DOMAIN
            )
        )
    ):
        raise ValueError(
            "MCX listing contains non-official URL."
        )

    return url


def parse_mcx_circular_listing_html(
    html: str,
    *,
    observed_at: datetime,
) -> tuple[
    PrimaryNoticeListingCandidateV2,
    ...,
]:
    if (
        not isinstance(
            observed_at,
            datetime,
        )
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    if not isinstance(
        html,
        str,
    ):
        raise ValueError(
            "MCX circular listing must be text."
        )

    parser = _TableParser()

    parser.feed(
        html
    )

    parser.close()

    output = []
    seen = set()

    for row in parser.rows:
        if len(
            row
        ) < 4:
            continue

        date_text = (
            row[0][0]
            .strip()
        )

        try:
            source_date = (
                datetime.strptime(
                    date_text,
                    "%d %b %Y",
                ).date()
            )

        except ValueError:
            continue

        category = (
            row[1][0]
            .strip()
        )

        title = (
            row[2][0]
            .strip()
        )

        circular_number = (
            row[3][0]
            .strip()
        )

        if (
            not title
            or not circular_number
        ):
            continue

        source_url = (
            _official_url(
                row[2][1]
            )
        )

        if source_url is None:
            continue

        source_item_id = (
            "MCX-CIRCULAR-"
            + circular_number
        )

        key = (
            source_item_id,
            source_date,
            title,
            source_url,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        output.append(
            PrimaryNoticeListingCandidateV2(
                source_id="MCX",
                source_date=(
                    source_date
                ),
                title=title,
                source_url=(
                    source_url
                ),
                observed_at=(
                    observed_at
                ),
                source_item_id=(
                    source_item_id
                ),
                category=(
                    category
                    or None
                ),
                timestamp_precision=(
                    "DATE_ONLY"
                ),
            )
        )

    return tuple(
        output
    )


class MCXCircularListingAdapterV2:
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

    def fetch_candidates(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        PrimaryNoticeListingCandidateV2,
        ...,
    ]:
        html = (
            self.transport
            .fetch_text(
                MCX_CIRCULAR_LISTING_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        return (
            parse_mcx_circular_listing_html(
                html,
                observed_at=(
                    observed_at
                ),
            )
        )
