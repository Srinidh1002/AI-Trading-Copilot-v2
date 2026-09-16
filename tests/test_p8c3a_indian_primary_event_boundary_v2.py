from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from services.contracts.indian_primary_notice_v2 import (
    IndianPrimaryNoticeV2,
)
from services.core.authoritative_event_registry_v2 import (
    new_authoritative_event_registry_v2,
)
from services.core.indian_primary_event_classifier_v2 import (
    build_authoritative_event_from_primary_notice_v2,
    classify_indian_primary_notice_v2,
)


PUBLISHED = datetime(
    2026,
    9,
    16,
    7,
    0,
    tzinfo=timezone.utc,
)

OBSERVED = (
    PUBLISHED
    + timedelta(
        seconds=2
    )
)


def notice(
    *,
    source_id,
    notice_kind,
    title,
    source_url,
    symbols=(),
    detail_text=None,
    source_item_id=None,
):
    return IndianPrimaryNoticeV2(
        source_id=source_id,
        notice_kind=notice_kind,
        title=title,
        published_at=PUBLISHED,
        source_url=source_url,
        source_item_id=(
            source_item_id
        ),
        detail_text=(
            detail_text
        ),
        affected_symbols=(
            symbols
        ),
    )


def test_notice_requires_timezone_aware_publication_time():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        IndianPrimaryNoticeV2(
            source_id="SEBI",
            notice_kind="CIRCULAR",
            title="Test circular",
            published_at=datetime(
                2026,
                9,
                16,
                12,
                0,
            ),
            source_url=(
                "https://www.sebi.gov.in/"
            ),
        )


def test_classifier_rejects_source_url_domain_mismatch():
    item = notice(
        source_id="SEBI",
        notice_kind="CIRCULAR",
        title="Review of position limits",
        source_url=(
            "https://example.com/circular"
        ),
    )

    with pytest.raises(
        ValueError,
        match="authoritative source domain",
    ):
        classify_indian_primary_notice_v2(
            item
        )


def test_rbi_mpc_policy_becomes_high_central_bank_policy():
    item = notice(
        source_id="RBI",
        notice_kind="PRESS_RELEASE",
        title=(
            "Monetary Policy Committee "
            "(MPC) Meeting"
        ),
        source_url=(
            "https://www.rbi.org.in/"
            "Scripts/BS_PressReleaseDisplay.aspx"
        ),
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
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

    assert (
        classified.market_scope_policy
        == "SOURCE_DEFAULT"
    )


def test_rbi_mpc_minutes_are_separate_from_policy_decision():
    item = notice(
        source_id="RBI",
        notice_kind="PRESS_RELEASE",
        title=(
            "Minutes of the Monetary "
            "Policy Committee Meeting"
        ),
        source_url=(
            "https://www.rbi.org.in/"
            "Scripts/BS_PressReleaseDisplay.aspx"
        ),
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "CENTRAL_BANK_MINUTES"
    )


def test_routine_rbi_penalty_is_not_promoted_to_market_event():
    item = notice(
        source_id="RBI",
        notice_kind="PRESS_RELEASE",
        title=(
            "RBI imposes monetary penalty "
            "on Example Bank Limited"
        ),
        source_url=(
            "https://www.rbi.org.in/"
            "Scripts/BS_PressReleaseDisplay.aspx"
        ),
    )

    assert (
        classify_indian_primary_notice_v2(
            item
        )
        is None
    )


def test_sebi_position_limit_circular_is_high_marketwide_event():
    item = notice(
        source_id="SEBI",
        notice_kind="CIRCULAR",
        title=(
            "Review of Position Limits for "
            "Clients and Penalty Provisions"
        ),
        source_url=(
            "https://www.sebi.gov.in/"
            "sebiweb/home/HomeAction.do"
        ),
        source_item_id="SEBI-PL-20260909",
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "POSITION_LIMIT_CHANGE"
    )

    assert (
        classified.severity
        == "HIGH"
    )

    event = (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
        )
    )

    assert event is not None

    assert (
        event.affected_markets
        == (
            "NIFTY",
            "SENSEX",
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        )
    )


def test_mcx_contract_launch_calendar_is_contract_change():
    item = notice(
        source_id="MCX",
        notice_kind="CIRCULAR",
        title=(
            "Modification in Contract Launch "
            "Calendar of Crude Oil and "
            "Crude Oil Mini Futures Contracts"
        ),
        source_url=(
            "https://www.mcxindia.com/"
            "circulars/all-circulars"
        ),
        source_item_id="MCX-485",
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "CONTRACT_SPEC_CHANGE"
    )

    event = (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
        )
    )

    assert event is not None

    assert (
        event.affected_markets
        == (
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        )
    )


def test_nse_financial_result_remains_symbol_scoped_before_resolution():
    item = notice(
        source_id="NSE",
        notice_kind=(
            "CORPORATE_ANNOUNCEMENT"
        ),
        title=(
            "Financial Results"
        ),
        detail_text=(
            "Quarterly financial results"
        ),
        symbols=(
            "RELIANCE",
        ),
        source_url=(
            "https://www.nseindia.com/"
            "companies-listing/"
            "corporate-filings-announcements"
        ),
        source_item_id="NSE-RESULT-1",
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "EARNINGS_RESULT"
    )

    assert (
        classified.market_scope_policy
        == "SYMBOL_RESOLUTION_REQUIRED"
    )

    assert (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
        )
        is None
    )


def test_nse_financial_result_can_become_nifty_event_after_resolution():
    item = notice(
        source_id="NSE",
        notice_kind=(
            "CORPORATE_ANNOUNCEMENT"
        ),
        title=(
            "Financial Results"
        ),
        symbols=(
            "RELIANCE",
        ),
        source_url=(
            "https://www.nseindia.com/"
            "companies-listing/"
            "corporate-filings-announcements"
        ),
        source_item_id="NSE-RESULT-2",
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    event = (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
            resolved_markets=(
                "NIFTY",
            ),
        )
    )

    assert event is not None

    assert (
        event.affected_markets
        == (
            "NIFTY",
        )
    )

    assert (
        event.affected_symbols
        == (
            "RELIANCE",
        )
    )


def test_bse_material_disclosure_does_not_auto_affect_sensex():
    item = notice(
        source_id="BSE",
        notice_kind=(
            "CORPORATE_ANNOUNCEMENT"
        ),
        title=(
            "Announcement under "
            "Regulation 30 (LODR)"
        ),
        symbols=(
            "532540",
        ),
        source_url=(
            "https://m.bseindia.com/"
            "corporates.aspx"
        ),
        source_item_id="BSE-ANN-1",
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    assert (
        classified.event_type
        == "COMPANY_DISCLOSURE"
    )

    assert (
        classified.severity
        == "MEDIUM"
    )

    assert (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
        )
        is None
    )


def test_company_disclosure_cannot_resolve_to_commodity_market():
    item = notice(
        source_id="NSE",
        notice_kind=(
            "CORPORATE_ANNOUNCEMENT"
        ),
        title="Financial Results",
        symbols=(
            "RELIANCE",
        ),
        source_url=(
            "https://www.nseindia.com/"
            "companies-listing/"
            "corporate-filings-announcements"
        ),
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    with pytest.raises(
        ValueError,
        match="unsupported market",
    ):
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
            resolved_markets=(
                "CRUDEOILM",
            ),
        )


def test_company_disclosure_without_symbol_fails_closed():
    item = notice(
        source_id="NSE",
        notice_kind=(
            "CORPORATE_ANNOUNCEMENT"
        ),
        title="Financial Results",
        source_url=(
            "https://www.nseindia.com/"
            "companies-listing/"
            "corporate-filings-announcements"
        ),
    )

    assert (
        classify_indian_primary_notice_v2(
            item
        )
        is None
    )


def test_authoritative_unscheduled_event_still_does_not_auto_block():
    item = notice(
        source_id="SEBI",
        notice_kind="CIRCULAR",
        title=(
            "Review of Position Limits "
            "for Clients"
        ),
        source_url=(
            "https://www.sebi.gov.in/"
            "sebiweb/home/HomeAction.do"
        ),
    )

    classified = (
        classify_indian_primary_notice_v2(
            item
        )
    )

    assert classified is not None

    event = (
        build_authoritative_event_from_primary_notice_v2(
            classified,
            observed_at=(
                OBSERVED
            ),
        )
    )

    assert event is not None

    registry = (
        new_authoritative_event_registry_v2()
    )

    registry.register(
        event
    )

    payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=(
                OBSERVED
                + timedelta(
                    minutes=1
                )
            ),
        )
    )

    assert (
        payload[
            "block_entries"
        ]
        is False
    )


def test_p8c3a_contains_no_network_broker_or_order_authority():
    paths = (
        Path(
            "services/contracts/"
            "indian_primary_notice_v2.py"
        ),
        Path(
            "services/core/"
            "indian_primary_event_classifier_v2.py"
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
        "requests.get(",
        "requests.post(",
        "httpx.",
        "aiohttp",
        "SmartConnect",
        "fyers_apiv3",
        "placeOrder(",
        "place_order",
        "submit_order",
        "BUY_CALL",
        "BUY_PUT",
        "certification_counter",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
