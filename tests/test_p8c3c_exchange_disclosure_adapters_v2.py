from pathlib import Path

from datetime import (
    datetime,
    timezone,
)
import json

import pytest

from services.contracts.exchange_disclosure_candidate_v2 import (
    ExchangeDisclosureCandidateV2,
)
from services.core.bse_corporate_announcement_adapter_v2 import (
    BSE_CORPORATE_ANNOUNCEMENTS_URL,
    BSECorporateAnnouncementAdapterV2,
    discover_bse_corporate_announcement_details,
    parse_bse_corporate_announcement_detail_html,
)
from services.core.nse_corporate_announcement_adapter_v2 import (
    NSE_CORPORATE_ANNOUNCEMENTS_URL,
    NSECorporateAnnouncementAdapterV2,
    parse_nse_corporate_announcements_json,
)


OBSERVED_AT = datetime(
    2026,
    9,
    16,
    18,
    30,
    tzinfo=timezone.utc,
)


NSE_RECORDS = [
    {
        "an_dt": "16-Sep-2026 23:25:33",
        "attchmntFile": (
            "https://nsearchives.nseindia.com/"
            "corporate/pnb_test.pdf"
        ),
        "attchmntText": (
            "Punjab National Bank has informed the "
            "Exchange about General Updates"
        ),
        "desc": "General Updates",
        "difference": "00:00:02",
        "exchdisstime": "16-Sep-2026 23:25:35",
        "seq_id": 106782619,
        "smIndustry": "Banks",
        "sm_isin": "INE160A01014",
        "sm_name": "Punjab National Bank",
        "sort_date": "2026-09-16 23:25:33",
        "symbol": "PNB",
    },
    {
        "an_dt": "16-Sep-2026 23:08:40",
        "attchmntFile": (
            "https://nsearchives.nseindia.com/"
            "corporate/policybzr_test.pdf"
        ),
        "attchmntText": (
            "PB Fintech Limited has informed the Exchange "
            "about Disclosure under Regulation 30."
        ),
        "desc": "General Updates",
        "difference": "00:00:00",
        "exchdisstime": "16-Sep-2026 23:08:40",
        "seq_id": "106782565",
        "sm_isin": "INE417T01026",
        "sm_name": "PB Fintech Limited",
        "sort_date": "2026-09-16 23:08:40",
        "symbol": "POLICYBZR",
    },
]


BSE_DETAIL_URL = (
    "https://m.bseindia.com/"
    "MAnnDet.aspx"
    "?newsid=38135E88-BB56-4056-9B8E-98F17A6575E3"
    "&flag=C&type=A&scrip_CD=544808"
)


BSE_LISTING_TEXT = (
    "Aastha Spintex Ltd "
    "-Alteration Of Authorized Share Capital "
    ", Sep 16 2026 , 11:30PM"
)


BSE_LISTING_HTML = f"""\
<html>
<body>
<a href="{BSE_DETAIL_URL}">
{BSE_LISTING_TEXT}
</a>
</body>
</html>
"""


BSE_DETAIL_HTML = """\
<html>
<body>
<table>
<tr>
<td>Security Code</td>
<td>544808</td>
</tr>
<tr>
<td>Company</td>
<td>Aastha Spintex Ltd</td>
</tr>
<tr>
<td>Exchange Received Time</td>
<td>16/09/2026 23:30:23</td>
</tr>
<tr>
<td>Exchange Disseminated Time</td>
<td>16/09/2026 23:30:23</td>
</tr>
<tr>
<td>Time Taken</td>
<td>00:00:00</td>
</tr>
</table>
<strong id="ist">
16 Sep 26|23:31 (IST)
</strong>
</body>
</html>
"""


class SinglePayloadTransport:
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


class MappingTransport:
    def __init__(
        self,
        mapping,
    ):
        self.mapping = mapping
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

        return self.mapping[
            url
        ]


def test_candidate_preserves_local_time_without_zone():
    candidate = (
        ExchangeDisclosureCandidateV2(
            source_id="NSE",
            disclosure_kind=(
                "CORPORATE_ANNOUNCEMENT"
            ),
            company_name="Example Ltd",
            title="General Updates",
            source_item_id="123",
            source_url=(
                NSE_CORPORATE_ANNOUNCEMENTS_URL
            ),
            observed_at=OBSERVED_AT,
            raw_primary_time=(
                "16-Sep-2026 23:25:33"
            ),
            primary_time_local=(
                datetime(
                    2026,
                    9,
                    16,
                    23,
                    25,
                    33,
                )
            ),
            primary_time_semantics=(
                "NSE_AN_DT"
            ),
            exchange_symbol="abc",
        )
    )

    assert (
        candidate.exchange_symbol
        == "ABC"
    )

    assert (
        candidate.primary_time_local.tzinfo
        is None
    )

    assert (
        candidate.timestamp_precision
        == "LOCAL_DATETIME_NO_ZONE"
    )

    assert (
        candidate.timezone_status
        == "SOURCE_UNSPECIFIED"
    )


def test_candidate_rejects_aware_local_exchange_timestamp():
    with pytest.raises(
        ValueError,
        match="timezone-naive",
    ):
        ExchangeDisclosureCandidateV2(
            source_id="NSE",
            disclosure_kind=(
                "CORPORATE_ANNOUNCEMENT"
            ),
            company_name="Example Ltd",
            title="General Updates",
            source_item_id="123",
            source_url=(
                NSE_CORPORATE_ANNOUNCEMENTS_URL
            ),
            observed_at=OBSERVED_AT,
            raw_primary_time=(
                "16-Sep-2026 23:25:33"
            ),
            primary_time_local=(
                datetime(
                    2026,
                    9,
                    16,
                    23,
                    25,
                    33,
                    tzinfo=timezone.utc,
                )
            ),
            primary_time_semantics=(
                "NSE_AN_DT"
            ),
            exchange_symbol="ABC",
        )


def test_nse_parser_preserves_identity_and_source_times():
    candidates = (
        parse_nse_corporate_announcements_json(
            json.dumps(
                NSE_RECORDS
            ),
            observed_at=OBSERVED_AT,
        )
    )

    assert len(
        candidates
    ) == 2

    first = candidates[0]

    assert (
        first.source_id
        == "NSE"
    )

    assert (
        first.source_item_id
        == "106782619"
    )

    assert (
        first.exchange_symbol
        == "PNB"
    )

    assert (
        first.isin
        == "INE160A01014"
    )

    assert (
        first.raw_primary_time
        == "16-Sep-2026 23:25:33"
    )

    assert (
        first.raw_disseminated_time
        == "16-Sep-2026 23:25:35"
    )

    assert (
        first.primary_time_local.tzinfo
        is None
    )

    assert (
        first.disseminated_time_local.tzinfo
        is None
    )

    assert (
        first.attachment_url
        == (
            "https://nsearchives.nseindia.com/"
            "corporate/pnb_test.pdf"
        )
    )


def test_nse_detail_text_retains_regulation_30_evidence():
    candidates = (
        parse_nse_corporate_announcements_json(
            json.dumps(
                NSE_RECORDS
            ),
            observed_at=OBSERVED_AT,
        )
    )

    second = candidates[1]

    assert (
        "Regulation 30"
        in second.detail_text
    )


def test_nse_duplicate_seq_id_is_collapsed():
    records = (
        NSE_RECORDS
        + [
            dict(
                NSE_RECORDS[0]
            )
        ]
    )

    candidates = (
        parse_nse_corporate_announcements_json(
            json.dumps(
                records
            ),
            observed_at=OBSERVED_AT,
        )
    )

    assert len(
        candidates
    ) == 2


def test_nse_nonofficial_attachment_is_rejected():
    records = [
        dict(
            NSE_RECORDS[0],
            attchmntFile=(
                "https://example.com/"
                "fake.pdf"
            ),
        )
    ]

    with pytest.raises(
        ValueError,
        match="official NSE HTTPS domain",
    ):
        parse_nse_corporate_announcements_json(
            json.dumps(
                records
            ),
            observed_at=OBSERVED_AT,
        )


def test_nse_adapter_calls_proven_official_route():
    transport = (
        SinglePayloadTransport(
            json.dumps(
                NSE_RECORDS
            )
        )
    )

    adapter = (
        NSECorporateAnnouncementAdapterV2(
            transport
        )
    )

    candidates = (
        adapter.fetch_candidates(
            observed_at=OBSERVED_AT,
        )
    )

    assert len(
        candidates
    ) == 2

    assert (
        transport.calls[0][0]
        == NSE_CORPORATE_ANNOUNCEMENTS_URL
    )



def test_bse_listing_excludes_source_explicit_mutual_fund_rows():
    mutual_fund_url = (
        "https://m.bseindia.com/"
        "MAnnDet.aspx"
        "?newsid=AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        "&flag=C&type=A&scrip_CD=544653"
    )

    html = f"""\
<html>
<body>
<a href="{mutual_fund_url}">
Titanium Hybrid Long-Short Fund Regular Plan Growth
-Compliances-Reg. 90 (1) Declaration of NAV - Mutual Fund
, Sep 16 2026 , 11:40PM
</a>
<a href="{BSE_DETAIL_URL}">
{BSE_LISTING_TEXT}
</a>
</body>
</html>
"""

    details = (
        discover_bse_corporate_announcement_details(
            html
        )
    )

    assert details == (
        (
            BSE_LISTING_TEXT,
            BSE_DETAIL_URL,
        ),
    )


def test_bse_listing_discovers_official_detail_link():
    details = (
        discover_bse_corporate_announcement_details(
            BSE_LISTING_HTML
        )
    )

    assert details == (
        (
            BSE_LISTING_TEXT,
            BSE_DETAIL_URL,
        ),
    )


def test_bse_detail_preserves_security_identity_and_local_times():
    candidate = (
        parse_bse_corporate_announcement_detail_html(
            BSE_DETAIL_HTML,
            detail_url=(
                BSE_DETAIL_URL
            ),
            listing_text=(
                BSE_LISTING_TEXT
            ),
            observed_at=OBSERVED_AT,
        )
    )

    assert candidate is not None

    assert (
        candidate.source_id
        == "BSE"
    )

    assert (
        candidate.source_item_id
        == (
            "38135E88-BB56-4056-"
            "9B8E-98F17A6575E3"
        )
    )

    assert (
        candidate.security_code
        == "544808"
    )

    assert (
        candidate.company_name
        == "Aastha Spintex Ltd"
    )

    assert (
        candidate.title
        == (
            "Alteration Of "
            "Authorized Share Capital"
        )
    )

    assert (
        candidate.raw_primary_time
        == "16/09/2026 23:30:23"
    )

    assert (
        candidate.raw_disseminated_time
        == "16/09/2026 23:30:23"
    )

    assert (
        candidate.primary_time_local.tzinfo
        is None
    )

    assert (
        candidate.timezone_status
        == "SOURCE_UNSPECIFIED"
    )


def test_bse_footer_ist_is_not_promoted_into_candidate_timezone():
    candidate = (
        parse_bse_corporate_announcement_detail_html(
            BSE_DETAIL_HTML,
            detail_url=(
                BSE_DETAIL_URL
            ),
            listing_text=(
                BSE_LISTING_TEXT
            ),
            observed_at=OBSERVED_AT,
        )
    )

    assert candidate is not None

    assert (
        candidate.timestamp_precision
        == "LOCAL_DATETIME_NO_ZONE"
    )

    assert (
        candidate.timezone_status
        == "SOURCE_UNSPECIFIED"
    )

    assert (
        candidate.primary_time_local.tzinfo
        is None
    )


def test_bse_security_code_identity_mismatch_fails_closed():
    bad_html = (
        BSE_DETAIL_HTML.replace(
            "<td>544808</td>",
            "<td>999999</td>",
            1,
        )
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        parse_bse_corporate_announcement_detail_html(
            bad_html,
            detail_url=(
                BSE_DETAIL_URL
            ),
            listing_text=(
                BSE_LISTING_TEXT
            ),
            observed_at=OBSERVED_AT,
        )


def test_bse_adapter_fetches_listing_then_detail():
    transport = MappingTransport(
        {
            BSE_CORPORATE_ANNOUNCEMENTS_URL:
                BSE_LISTING_HTML,
            BSE_DETAIL_URL:
                BSE_DETAIL_HTML,
        }
    )

    adapter = (
        BSECorporateAnnouncementAdapterV2(
            transport,
            max_details=5,
        )
    )

    candidates = (
        adapter.fetch_candidates(
            observed_at=OBSERVED_AT,
        )
    )

    assert len(
        candidates
    ) == 1

    assert len(
        transport.calls
    ) == 2


def test_bse_adapter_detail_limit_is_bounded():
    with pytest.raises(
        ValueError,
        match="between 1 and 100",
    ):
        BSECorporateAnnouncementAdapterV2(
            object(),
            max_details=101,
        )


def test_exchange_disclosure_foundation_has_no_direct_event_or_trade_authority():
    paths = (
        Path(
            "services/contracts/"
            "exchange_disclosure_candidate_v2.py"
        ),
        Path(
            "services/core/"
            "nse_corporate_announcement_adapter_v2.py"
        ),
        Path(
            "services/core/"
            "bse_corporate_announcement_adapter_v2.py"
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
        "build_authoritative_event",
        "ZoneInfo(",
        "Asia/Kolkata",
        "timezone(timedelta(",
        "BUY_CALL",
        "BUY_PUT",
        "placeOrder(",
        "place_order",
        "submit_order",
        "certification_counter",
        "live_execution_eligible = True",
        "broker_submission = True",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
