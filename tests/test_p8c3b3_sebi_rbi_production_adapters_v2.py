from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from services.core.indian_primary_event_classifier_v2 import (
    classify_indian_primary_notice_v2,
)
from services.core.rbi_press_release_rss_adapter_v2 import (
    RBI_PRESS_RELEASE_RSS_URL,
    RBIPressReleaseRSSAdapterV2,
    parse_rbi_press_release_rss_candidates,
    promote_rbi_candidate_to_notice,
    promote_rbi_candidates_to_notices,
)
from services.core.sebi_circular_listing_adapter_v2 import (
    parse_sebi_circular_listing_html,
)


OBSERVED_AT = datetime(
    2026,
    9,
    16,
    17,
    30,
    tzinfo=timezone.utc,
)


SEBI_MALFORMED_LIVE_SHAPE = """\
<table>
<tr role='row' class='odd'>
<td>Sep 09, 2026</td>
<td><a href="https://www.sebi.gov.in/legal/circulars/sep-2026/review-of-position-limits_104387.html">
Review of Position Limits for Clients
</a>
</tr>
</table>
"""


SEBI_WELL_FORMED = """\
<table>
<tr>
<td>Sep 07, 2026</td>
<td>
<a href="https://www.sebi.gov.in/legal/circulars/sep-2026/ease-of-regulatory-compliances_104319.html">
Ease of regulatory compliances for FPIs
</a>
</td>
</tr>
</table>
"""


RBI_NO_ZONE_FIXTURE = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
<channel>

<item>
<title>Monetary Policy Committee (MPC) Meeting</title>
<link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=60001</link>
<pubDate>Wed, 16 Sep 2026 14:05:30</pubDate>
<description><![CDATA[
<p>Monetary Policy Committee meeting and policy communication.</p>
]]></description>
</item>

<item>
<title>Conversion/Switch of Government of India Securities</title>
<link>https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=60002</link>
<pubDate>Wed, 16 Sep 2026 13:35:00</pubDate>
</item>

</channel>
</rss>
"""


RBI_EXPLICIT_ZONE_FIXTURE = """\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
<channel>

<item>
<title>Monetary Policy Committee (MPC) Meeting</title>
<link>http://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=60003</link>
<guid>RBI-PR-60003</guid>
<pubDate>Wed, 16 Sep 2026 14:05:30 +0530</pubDate>
<description><![CDATA[
<p>Monetary Policy Committee policy communication.</p>
]]></description>
</item>

</channel>
</rss>
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


def test_sebi_parser_recovers_live_row_missing_final_td_close():
    candidates = (
        parse_sebi_circular_listing_html(
            SEBI_MALFORMED_LIVE_SHAPE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 1

    assert (
        candidates[0]
        .source_date
        .isoformat()
        == "2026-09-09"
    )

    assert (
        candidates[0]
        .timestamp_precision
        == "DATE_ONLY"
    )


def test_sebi_parser_still_accepts_well_formed_rows():
    candidates = (
        parse_sebi_circular_listing_html(
            SEBI_WELL_FORMED,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 1


def test_rbi_normal_utf8_bom_is_recovered():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            "\ufeff"
            + RBI_NO_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 2


def test_rbi_latin1_bom_mojibake_is_recovered():
    raw = (
        "\ufeff"
        + RBI_NO_ZONE_FIXTURE
    ).encode(
        "utf-8"
    )

    mojibake = raw.decode(
        "latin-1"
    )

    assert mojibake.startswith(
        "ï»¿"
    )

    candidates = (
        parse_rbi_press_release_rss_candidates(
            mojibake,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 2


def test_rbi_no_zone_pubdate_is_preserved_not_invented():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_NO_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    candidate = candidates[0]

    assert (
        candidate.timestamp_precision
        == "LOCAL_DATETIME_NO_ZONE"
    )

    assert (
        candidate.timezone_status
        == "SOURCE_UNSPECIFIED"
    )

    assert (
        candidate.source_published_at.tzinfo
        is None
    )

    assert (
        candidate.raw_pub_date
        == (
            "Wed, 16 Sep 2026 "
            "14:05:30"
        )
    )


def test_rbi_no_zone_candidate_cannot_be_promoted():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_NO_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert (
        promote_rbi_candidate_to_notice(
            candidates[0]
        )
        is None
    )

    assert (
        promote_rbi_candidates_to_notices(
            candidates
        )
        == ()
    )


def test_rbi_explicit_source_zone_can_be_promoted():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_EXPLICIT_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 1

    candidate = candidates[0]

    assert (
        candidate.timestamp_precision
        == "DATETIME_WITH_ZONE"
    )

    assert (
        candidate.timezone_status
        == "SOURCE_EXPLICIT"
    )

    assert (
        candidate.source_published_at
        .utcoffset()
        is not None
    )

    notice = (
        promote_rbi_candidate_to_notice(
            candidate
        )
    )

    assert notice is not None

    assert (
        notice.published_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            16,
            8,
            35,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_rbi_http_official_link_is_canonicalized_to_https():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_EXPLICIT_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert (
        candidates[0]
        .source_url
        .startswith(
            "https://www.rbi.org.in/"
        )
    )


def test_rbi_cross_domain_url_is_rejected():
    payload = (
        RBI_NO_ZONE_FIXTURE
        .replace(
            (
                "https://www.rbi.org.in/"
                "scripts/"
                "BS_PressReleaseDisplay.aspx"
                "?prid=60001"
            ),
            "https://example.com/item",
        )
    )

    with pytest.raises(
        ValueError,
        match="authoritative RBI domain",
    ):
        parse_rbi_press_release_rss_candidates(
            payload,
            observed_at=(
                OBSERVED_AT
            ),
        )


def test_rbi_visible_description_is_preserved():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_NO_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert (
        candidates[0]
        .detail_text
        == (
            "Monetary Policy Committee "
            "meeting and policy communication."
        )
    )


def test_rbi_explicitly_timed_policy_notice_uses_existing_classifier():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_EXPLICIT_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    notice = (
        promote_rbi_candidate_to_notice(
            candidates[0]
        )
    )

    assert notice is not None

    classified = (
        classify_indian_primary_notice_v2(
            notice
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "CENTRAL_BANK_POLICY"
    )

    assert (
        classified.severity
        == "HIGH"
    )


def test_rbi_adapter_exposes_candidates_but_notices_require_zone():
    adapter = (
        RBIPressReleaseRSSAdapterV2(
            FixtureTransport(
                RBI_NO_ZONE_FIXTURE
            )
        )
    )

    candidates = (
        adapter.fetch_candidates(
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        candidates
    ) == 2

    notices = (
        adapter.fetch_notices(
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert notices == ()


def test_rbi_adapter_uses_official_rss_url():
    transport = (
        FixtureTransport(
            RBI_NO_ZONE_FIXTURE
        )
    )

    adapter = (
        RBIPressReleaseRSSAdapterV2(
            transport
        )
    )

    adapter.fetch_candidates(
        observed_at=(
            OBSERVED_AT
        ),
    )

    assert (
        transport.calls[0][0]
        == RBI_PRESS_RELEASE_RSS_URL
    )


def test_rbi_fetch_or_observed_time_never_becomes_publication_time():
    candidates = (
        parse_rbi_press_release_rss_candidates(
            RBI_NO_ZONE_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    for candidate in candidates:
        assert (
            candidate.source_published_at
            != OBSERVED_AT.replace(
                tzinfo=None
            )
        )

        assert (
            candidate.timezone_status
            == "SOURCE_UNSPECIFIED"
        )


def test_p8c3b3_contains_no_trading_or_direct_event_authority():
    paths = (
        Path(
            "services/core/"
            "sebi_circular_listing_adapter_v2.py"
        ),
        Path(
            "services/core/"
            "rbi_press_release_rss_adapter_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path
        in paths
    )

    forbidden = (
        "AuthoritativeMarketEventV2(",
        "build_event_risk_payload",
        "requests.get(",
        "requests.post(",
        "SmartConnect",
        "fyers_apiv3",
        "placeOrder(",
        "place_order",
        "submit_order",
        "BUY_CALL",
        "BUY_PUT",
        "certification_counter",
        "ZoneInfo(",
        'timezone(timedelta(hours=5, minutes=30))',
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
