from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.contracts.primary_notice_listing_candidate_v2 import (
    PrimaryNoticeListingCandidateV2,
)
from services.core.mcx_circular_listing_adapter_v2 import (
    MCX_CIRCULAR_LISTING_URL,
    MCXCircularListingAdapterV2,
    parse_mcx_circular_listing_html,
)
from services.core.sebi_circular_listing_adapter_v2 import (
    SEBI_CIRCULAR_LISTING_URL,
    SEBICircularListingAdapterV2,
    parse_sebi_circular_listing_html,
)


OBSERVED_AT = datetime(
    2026,
    9,
    16,
    16,
    30,
    tzinfo=timezone.utc,
)


SEBI_FIXTURE = """\
<html>
<body>
<table>
<tr>
<th>Date</th>
<th>Title</th>
</tr>

<tr>
<td>Sep 09, 2026</td>
<td>
<a href="/legal/circulars/sep-2026/review-of-position-limits.html">
Review of Position Limits for Clients and Penalty Provisions
</a>
</td>
</tr>

<tr>
<td>Sep 07, 2026</td>
<td>
<a href="/legal/circulars/sep-2026/ease-of-regulatory-compliances.html">
Ease of regulatory compliances for FPIs
</a>
</td>
</tr>
</table>
</body>
</html>
"""


MCX_FIXTURE = """\
<html>
<body>
<table>
<tr>
<th>Date</th>
<th>Category</th>
<th>Title</th>
<th>Circular No.</th>
</tr>

<tr>
<td>15 Sep 2026</td>
<td>TECH</td>
<td>
<a href="/docs/default-source/circulars/520.pdf">
Introduction of Separate Product IDs &amp; Product Name
</a>
</td>
<td>520</td>
</tr>

<tr>
<td>09 Sep 2026</td>
<td>T&amp;S</td>
<td>
<a href="/docs/default-source/circulars/513.pdf">
Review of Position Limits for Clients
</a>
</td>
<td>513</td>
</tr>
</table>
</body>
</html>
"""


class FixtureTransport:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload
        self.calls = []

    def fetch_text(
        self,
        url,
        *,
        accepted_content_types,
    ):
        self.calls.append(
            (
                url,
                accepted_content_types,
            )
        )

        return self.payload


def test_candidate_requires_timezone_aware_observed_at():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        PrimaryNoticeListingCandidateV2(
            source_id="SEBI",
            source_date=datetime(
                2026,
                9,
                9,
            ).date(),
            title="Test",
            source_url=(
                "https://www.sebi.gov.in/test"
            ),
            observed_at=datetime(
                2026,
                9,
                9,
            ),
        )


def test_sebi_listing_returns_date_only_candidates():
    candidates = (
        parse_sebi_circular_listing_html(
            SEBI_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 2

    first = candidates[0]

    assert first.source_id == "SEBI"

    assert (
        first.timestamp_precision
        == "DATE_ONLY"
    )

    assert not hasattr(
        first,
        "published_at",
    )


def test_sebi_listing_preserves_official_detail_url():
    candidate = (
        parse_sebi_circular_listing_html(
            SEBI_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )[0]
    )

    assert (
        candidate.source_url
        .startswith(
            "https://www.sebi.gov.in/"
        )
    )


def test_sebi_rejects_cross_domain_detail_link():
    html = SEBI_FIXTURE.replace(
        (
            "/legal/circulars/sep-2026/"
            "review-of-position-limits.html"
        ),
        (
            "https://example.com/"
            "malicious"
        ),
    )

    with pytest.raises(
        ValueError,
        match="non-official URL",
    ):
        parse_sebi_circular_listing_html(
            html,
            observed_at=(
                OBSERVED_AT
            ),
        )


def test_mcx_listing_preserves_category_and_circular_number():
    candidates = (
        parse_mcx_circular_listing_html(
            MCX_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 2

    assert (
        candidates[0]
        .source_item_id
        == "MCX-CIRCULAR-520"
    )

    assert (
        candidates[0]
        .category
        == "TECH"
    )

    assert (
        candidates[1]
        .category
        == "T&S"
    )


def test_mcx_listing_is_date_only_not_fake_midnight():
    candidate = (
        parse_mcx_circular_listing_html(
            MCX_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )[0]
    )

    assert (
        candidate.timestamp_precision
        == "DATE_ONLY"
    )

    assert not hasattr(
        candidate,
        "published_at",
    )


def test_mcx_rejects_cross_domain_detail_link():
    html = MCX_FIXTURE.replace(
        (
            "/docs/default-source/"
            "circulars/520.pdf"
        ),
        (
            "https://example.com/"
            "520.pdf"
        ),
    )

    with pytest.raises(
        ValueError,
        match="non-official URL",
    ):
        parse_mcx_circular_listing_html(
            html,
            observed_at=(
                OBSERVED_AT
            ),
        )


def test_sebi_adapter_uses_official_listing_url():
    transport = (
        FixtureTransport(
            SEBI_FIXTURE
        )
    )

    adapter = (
        SEBICircularListingAdapterV2(
            transport
        )
    )

    values = (
        adapter.fetch_candidates(
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(values) == 2

    assert (
        transport.calls[0][0]
        == SEBI_CIRCULAR_LISTING_URL
    )


def test_mcx_adapter_uses_official_listing_url():
    transport = (
        FixtureTransport(
            MCX_FIXTURE
        )
    )

    adapter = (
        MCXCircularListingAdapterV2(
            transport
        )
    )

    values = (
        adapter.fetch_candidates(
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(values) == 2

    assert (
        transport.calls[0][0]
        == MCX_CIRCULAR_LISTING_URL
    )


def test_duplicate_listing_rows_are_collapsed():
    sebi = (
        parse_sebi_circular_listing_html(
            SEBI_FIXTURE.replace(
                "</table>",
                (
                    """
<tr>
<td>Sep 09, 2026</td>
<td>
<a href="/legal/circulars/sep-2026/review-of-position-limits.html">
Review of Position Limits for Clients and Penalty Provisions
</a>
</td>
</tr>
</table>
"""
                ),
            ),
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        sebi
    ) == 2


def test_p8c3b1_has_no_event_promotion_or_trading_authority():
    paths = (
        Path(
            "services/contracts/"
            "primary_notice_listing_candidate_v2.py"
        ),
        Path(
            "services/core/"
            "sebi_circular_listing_adapter_v2.py"
        ),
        Path(
            "services/core/"
            "mcx_circular_listing_adapter_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "IndianPrimaryNoticeV2(",
        "AuthoritativeMarketEventV2(",
        "build_event_risk_payload",
        "requests.get(",
        "requests.post(",
        "SmartConnect",
        "fyers_apiv3",
        "placeOrder(",
        "place_order",
        "submit_order",
        "certification_counter",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
