"""BSE official corporate-announcement adapter.

The public BSE mobile announcements listing exposes stable ``newsid`` and
``scrip_CD`` values.  Its announcement-detail pages expose Security Code,
Company, Exchange Received Time and Exchange Disseminated Time.

The detail page also has a page clock marked IST, but P8C.3C does not use
that footer as proof that announcement-record timestamps themselves carry
explicit timezone provenance.  The record timestamps therefore remain
LOCAL_DATETIME_NO_ZONE.
"""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import (
    parse_qs,
    urljoin,
    urlparse,
)

from services.contracts.exchange_disclosure_candidate_v2 import (
    ExchangeDisclosureCandidateV2,
)


BSE_CORPORATE_ANNOUNCEMENTS_URL = (
    "https://m.bseindia.com/"
    "corporates.aspx"
)

BSE_DOMAIN = (
    "bseindia.com"
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


def _official_bse_url(
    value: str,
) -> str:
    url = urljoin(
        BSE_CORPORATE_ANNOUNCEMENTS_URL,
        value,
    )

    parsed = urlparse(
        url
    )

    host = (
        parsed.hostname
        or ""
    ).lower()

    if (
        parsed.scheme.lower()
        != "https"
        or not (
            host == BSE_DOMAIN
            or host.endswith(
                "." + BSE_DOMAIN
            )
        )
    ):
        raise ValueError(
            "BSE announcement URL escaped "
            "the official BSE HTTPS domain."
        )

    return url


def _query_value(
    parsed,
    name: str,
) -> str | None:
    query = parse_qs(
        parsed.query
    )

    for key, values in query.items():
        if (
            key.lower()
            == name.lower()
            and values
        ):
            return _text(
                values[0]
            )

    return None


def _parse_bse_local_time(
    value: str | None,
) -> datetime | None:
    text = _text(
        value
    )

    if text is None:
        return None

    try:
        return datetime.strptime(
            text,
            "%d/%m/%Y %H:%M:%S",
        )

    except ValueError:
        return None


class _BSEListingParser(
    HTMLParser
):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.links: list[
            tuple[
                str,
                str,
            ]
        ] = []

        self._href = None
        self._parts = None

    def handle_starttag(
        self,
        tag,
        attrs,
    ) -> None:
        if tag.lower() != "a":
            return

        values = dict(
            attrs
        )

        href = values.get(
            "href"
        )

        if not isinstance(
            href,
            str,
        ):
            return

        self._href = href
        self._parts = []

    def handle_data(
        self,
        data,
    ) -> None:
        if self._parts is not None:
            self._parts.append(
                data
            )

    def handle_endtag(
        self,
        tag,
    ) -> None:
        if (
            tag.lower() != "a"
            or self._parts is None
            or self._href is None
        ):
            return

        text = " ".join(
            "".join(
                self._parts
            ).split()
        )

        if text:
            self.links.append(
                (
                    text,
                    self._href,
                )
            )

        self._href = None
        self._parts = None


class _BSEDetailTableParser(
    HTMLParser
):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.rows: list[
            list[str]
        ] = []

        self._row = None
        self._cell = None

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


def discover_bse_corporate_announcement_details(
    html: str,
) -> tuple[
    tuple[
        str,
        str,
    ],
    ...,
]:
    if not isinstance(
        html,
        str,
    ):
        raise ValueError(
            "BSE listing must be text."
        )

    parser = (
        _BSEListingParser()
    )

    parser.feed(
        html
    )

    parser.close()

    output = []
    seen = set()

    for listing_text, href in parser.links:
        lower = href.lower()

        if (
            "manndet.aspx"
            not in lower
            and "anndet_new.aspx"
            not in lower
        ):
            continue

        # The live BSE corporate listing also publishes
        # mutual-fund NAV announcements through the same
        # announcement-detail surface.  This adapter is
        # intentionally restricted to company-equity
        # disclosure candidates for the later NIFTY/SENSEX
        # constituent-resolution path.
        #
        # Filter only source-explicit Mutual Fund rows here.
        # Do not infer security type from scrip-code ranges,
        # names, or other undocumented heuristics.
        if (
            "mutual fund"
            in listing_text.lower()
        ):
            continue

        detail_url = (
            _official_bse_url(
                href
            )
        )

        if detail_url in seen:
            continue

        seen.add(
            detail_url
        )

        output.append(
            (
                listing_text,
                detail_url,
            )
        )

    return tuple(
        output
    )


def _extract_listing_subject(
    listing_text: str,
    company_name: str,
) -> str:
    value = " ".join(
        listing_text.split()
    )

    value = re.sub(
        (
            r"\s*,\s*"
            r"[A-Za-z]{3}\s+"
            r"\d{1,2}\s+\d{4}"
            r"\s*,\s*"
            r"\d{1,2}:\d{2}"
            r"\s*(?:AM|PM)"
            r"\s*$"
        ),
        "",
        value,
        flags=re.IGNORECASE,
    )

    if (
        value[:len(company_name)]
        .lower()
        == company_name.lower()
    ):
        remainder = (
            value[
                len(company_name):
            ]
            .lstrip(
                " -–—:"
            )
            .strip()
        )

        if remainder:
            return remainder

    return value


def parse_bse_corporate_announcement_detail_html(
    html: str,
    *,
    detail_url: str,
    listing_text: str,
    observed_at: datetime,
) -> ExchangeDisclosureCandidateV2 | None:
    if not _aware(
        observed_at
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    if not isinstance(
        html,
        str,
    ):
        raise ValueError(
            "BSE announcement detail must be text."
        )

    source_url = (
        _official_bse_url(
            detail_url
        )
    )

    parsed_url = urlparse(
        source_url
    )

    news_id = _query_value(
        parsed_url,
        "newsid",
    )

    query_security_code = (
        _query_value(
            parsed_url,
            "scrip_CD",
        )
    )

    if (
        news_id is None
        or query_security_code
        is None
    ):
        raise ValueError(
            "BSE detail URL lacks stable "
            "announcement identity."
        )

    parser = (
        _BSEDetailTableParser()
    )

    parser.feed(
        html
    )

    parser.close()

    fields = {}

    for row in parser.rows:
        if len(row) < 2:
            continue

        key = (
            row[0]
            .strip()
        )

        value = (
            row[1]
            .strip()
        )

        if key in {
            "Security Code",
            "Company",
            "Exchange Received Time",
            "Exchange Disseminated Time",
            "Time Taken",
        }:
            fields[key] = value

    security_code = _text(
        fields.get(
            "Security Code"
        )
    )

    company_name = _text(
        fields.get(
            "Company"
        )
    )

    raw_received = _text(
        fields.get(
            "Exchange Received Time"
        )
    )

    raw_disseminated = _text(
        fields.get(
            "Exchange Disseminated Time"
        )
    )

    received_local = (
        _parse_bse_local_time(
            raw_received
        )
    )

    disseminated_local = (
        _parse_bse_local_time(
            raw_disseminated
        )
    )

    if (
        security_code is None
        or company_name is None
        or raw_received is None
        or received_local is None
    ):
        return None

    if (
        security_code
        != query_security_code
    ):
        raise ValueError(
            "BSE Security Code does not match "
            "the detail URL scrip_CD."
        )

    title = (
        _extract_listing_subject(
            listing_text,
            company_name,
        )
    )

    return (
        ExchangeDisclosureCandidateV2(
            source_id="BSE",
            disclosure_kind=(
                "CORPORATE_ANNOUNCEMENT"
            ),
            company_name=(
                company_name
            ),
            title=title,
            source_item_id=(
                news_id
            ),
            source_url=(
                source_url
            ),
            observed_at=(
                observed_at
            ),
            raw_primary_time=(
                raw_received
            ),
            primary_time_local=(
                received_local
            ),
            primary_time_semantics=(
                "BSE_EXCHANGE_RECEIVED_TIME"
            ),
            exchange_symbol=None,
            security_code=(
                security_code
            ),
            isin=None,
            detail_text=None,
            attachment_url=None,
            raw_disseminated_time=(
                raw_disseminated
                if (
                    disseminated_local
                    is not None
                )
                else None
            ),
            disseminated_time_local=(
                disseminated_local
            ),
            timestamp_precision=(
                "LOCAL_DATETIME_NO_ZONE"
            ),
            timezone_status=(
                "SOURCE_UNSPECIFIED"
            ),
        )
    )


class BSECorporateAnnouncementAdapterV2:
    def __init__(
        self,
        transport,
        *,
        max_details: int = 25,
    ) -> None:
        if transport is None:
            raise ValueError(
                "transport is required."
            )

        if (
            not isinstance(
                max_details,
                int,
            )
            or isinstance(
                max_details,
                bool,
            )
            or max_details < 1
            or max_details > 100
        ):
            raise ValueError(
                "max_details must be an integer "
                "between 1 and 100."
            )

        self.transport = (
            transport
        )

        self.max_details = (
            max_details
        )

    def fetch_candidates(
        self,
        *,
        observed_at: datetime,
    ) -> tuple[
        ExchangeDisclosureCandidateV2,
        ...,
    ]:
        listing = (
            self.transport
            .fetch_text(
                BSE_CORPORATE_ANNOUNCEMENTS_URL,
                accepted_content_types=(
                    "text/html",
                    "text/plain",
                ),
            )
        )

        details = (
            discover_bse_corporate_announcement_details(
                listing
            )
        )

        output = []
        seen = set()

        for (
            listing_text,
            detail_url,
        ) in details[
            :self.max_details
        ]:
            html = (
                self.transport
                .fetch_text(
                    detail_url,
                    accepted_content_types=(
                        "text/html",
                        "text/plain",
                    ),
                )
            )

            candidate = (
                parse_bse_corporate_announcement_detail_html(
                    html,
                    detail_url=(
                        detail_url
                    ),
                    listing_text=(
                        listing_text
                    ),
                    observed_at=(
                        observed_at
                    ),
                )
            )

            if candidate is None:
                continue

            if (
                candidate.source_item_id
                in seen
            ):
                continue

            seen.add(
                candidate.source_item_id
            )

            output.append(
                candidate
            )

        return tuple(
            output
        )
