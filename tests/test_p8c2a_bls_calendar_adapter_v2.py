from pathlib import Path
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from services.core.authoritative_event_registry_v2 import (
    new_authoritative_event_registry_v2,
)
from services.core.bls_calendar_adapter_v2 import (
    BLS_ICS_URL,
    BLSCalendarAdapterV2,
    parse_bls_calendar_ics,
)
from services.core.official_http_transport_v2 import (
    OfficialHttpTextTransportV2,
)


OBSERVED_AT = datetime(
    2026,
    9,
    1,
    12,
    0,
    tzinfo=timezone.utc,
)


BLS_FIXTURE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BLS//Calendar//EN
BEGIN:VEVENT
UID:bls-cpi-20260911
DTSTART;TZID=America/New_York:20260911T083000
SUMMARY:Consumer Price Index for August 2026
END:VEVENT
BEGIN:VEVENT
UID:bls-ppi-20260910
DTSTART;TZID=America/New_York:20260910T083000
SUMMARY:Producer Price Index for August 2026
END:VEVENT
BEGIN:VEVENT
UID:bls-jobs-20260904
DTSTART;TZID=America/New_York:20260904T083000
SUMMARY:Employment Situation for August 2026
END:VEVENT
BEGIN:VEVENT
UID:bls-jolts-20260929
DTSTART;TZID=America/New_York:20260929T100000
SUMMARY:Job Openings and Labor Turnover Survey for August 2026
END:VEVENT
BEGIN:VEVENT
UID:bls-holiday-20260907
DTSTART;VALUE=DATE:20260907
SUMMARY:Labor Day
END:VEVENT
BEGIN:VEVENT
UID:bls-irrelevant-20260924
DTSTART;TZID=America/New_York:20260924T100000
SUMMARY:Employee Benefits in the United States for March 2026
END:VEVENT
END:VCALENDAR
"""


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        content=b"",
        content_type="text/plain",
        location=None,
        encoding="utf-8",
    ):
        self.status_code = (
            status_code
        )

        self.content = (
            content
        )

        self.encoding = (
            encoding
        )

        self.headers = {
            "Content-Type":
            content_type,
        }

        if location is not None:
            self.headers[
                "Location"
            ] = location


class FakeSession:
    def __init__(
        self,
        responses,
    ):
        self.responses = list(
            responses
        )

        self.calls = []

    def get(
        self,
        url,
        **kwargs,
    ):
        self.calls.append(
            {
                "url": url,
                **kwargs,
            }
        )

        if not self.responses:
            raise AssertionError(
                "Unexpected HTTP call."
            )

        return self.responses.pop(
            0
        )


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


def test_official_transport_rejects_non_https_before_request():
    session = FakeSession(
        []
    )

    transport = (
        OfficialHttpTextTransportV2(
            allowed_domains=(
                "bls.gov",
            ),
            session=session,
        )
    )

    with pytest.raises(
        ValueError,
        match="HTTPS",
    ):
        transport.fetch_text(
            "http://www.bls.gov/"
        )

    assert session.calls == []


def test_official_transport_rejects_non_allowlisted_host():
    session = FakeSession(
        []
    )

    transport = (
        OfficialHttpTextTransportV2(
            allowed_domains=(
                "bls.gov",
            ),
            session=session,
        )
    )

    with pytest.raises(
        ValueError,
        match="allowlisted",
    ):
        transport.fetch_text(
            "https://example.com/"
        )

    assert session.calls == []


def test_official_transport_blocks_cross_domain_redirect():
    session = FakeSession(
        [
            FakeResponse(
                status_code=302,
                location=(
                    "https://example.com/"
                    "calendar.ics"
                ),
            )
        ]
    )

    transport = (
        OfficialHttpTextTransportV2(
            allowed_domains=(
                "bls.gov",
            ),
            session=session,
        )
    )

    with pytest.raises(
        ValueError,
        match="allowlisted",
    ):
        transport.fetch_text(
            BLS_ICS_URL,
        )

    assert len(
        session.calls
    ) == 1


def test_official_transport_allows_same_domain_redirect():
    session = FakeSession(
        [
            FakeResponse(
                status_code=302,
                location=(
                    "/schedule/"
                    "news_release/"
                    "bls-final.ics"
                ),
            ),
            FakeResponse(
                status_code=200,
                content=b"BEGIN:VCALENDAR\nEND:VCALENDAR",
                content_type="text/calendar",
            ),
        ]
    )

    transport = (
        OfficialHttpTextTransportV2(
            allowed_domains=(
                "bls.gov",
            ),
            session=session,
        )
    )

    text = transport.fetch_text(
        BLS_ICS_URL,
        accepted_content_types=(
            "text/calendar",
        ),
    )

    assert (
        "BEGIN:VCALENDAR"
        in text
    )

    assert len(
        session.calls
    ) == 2


def test_official_transport_enforces_response_size_limit():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                content=b"x" * 20,
                content_type="text/plain",
            )
        ]
    )

    transport = (
        OfficialHttpTextTransportV2(
            allowed_domains=(
                "bls.gov",
            ),
            max_bytes=10,
            session=session,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="size limit",
    ):
        transport.fetch_text(
            BLS_ICS_URL,
        )


def test_bls_parser_keeps_only_supported_market_relevant_releases():
    events = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        events
    ) == 4

    titles = {
        event.title
        for event in events
    }

    assert (
        "Consumer Price Index for August 2026"
        in titles
    )

    assert (
        "Employment Situation for August 2026"
        in titles
    )

    assert (
        "Labor Day"
        not in titles
    )

    assert (
        "Employee Benefits in the United States for March 2026"
        not in titles
    )


def test_bls_cpi_is_exact_timezone_aware_schedule():
    events = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    cpi = next(
        event
        for event in events
        if "Consumer Price Index"
        in event.title
    )

    assert (
        cpi.event_type
        == "INFLATION_RELEASE"
    )

    assert (
        cpi.severity
        == "HIGH"
    )

    assert (
        cpi.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            11,
            12,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_bls_employment_situation_is_high_severity_employment_event():
    events = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    jobs = next(
        event
        for event in events
        if "Employment Situation"
        in event.title
    )

    assert (
        jobs.event_type
        == "EMPLOYMENT_RELEASE"
    )

    assert jobs.severity == "HIGH"


def test_bls_events_apply_to_five_market_default_scope():
    events = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    for event in events:
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


def test_bls_parser_is_stable_and_idempotent():
    first = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    second = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert [
        event.event_id
        for event in first
    ] == [
        event.event_id
        for event in second
    ]


def test_adapter_uses_official_bls_ics_url():
    transport = (
        FixtureTransport(
            BLS_FIXTURE
        )
    )

    adapter = (
        BLSCalendarAdapterV2(
            transport
        )
    )

    events = adapter.fetch_events(
        observed_at=OBSERVED_AT,
    )

    assert len(events) == 4

    assert (
        transport.calls[0][0]
        == BLS_ICS_URL
    )


def test_bls_events_are_accepted_by_authoritative_registry():
    adapter = (
        BLSCalendarAdapterV2(
            FixtureTransport(
                BLS_FIXTURE
            )
        )
    )

    events = adapter.fetch_events(
        observed_at=OBSERVED_AT,
    )

    registry = (
        new_authoritative_event_registry_v2()
    )

    added = registry.register_many(
        events
    )

    assert added == 4


def test_official_bls_event_still_requires_explicit_block_policy():
    events = (
        parse_bls_calendar_ics(
            BLS_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    cpi = next(
        event
        for event in events
        if event.severity == "HIGH"
        and event.event_type
        == "INFLATION_RELEASE"
    )

    registry = (
        new_authoritative_event_registry_v2()
    )

    registry.register(
        cpi
    )

    now = (
        cpi.scheduled_at
        - timedelta(
            minutes=5
        )
    )

    default_payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=now,
        )
    )

    policy_payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=now,
            hard_block_event_types=(
                frozenset(
                    {
                        "INFLATION_RELEASE",
                    }
                )
            ),
        )
    )

    assert (
        default_payload[
            "block_entries"
        ]
        is False
    )

    assert (
        policy_payload[
            "block_entries"
        ]
        is True
    )


def test_p8c2a_contains_no_trading_or_broker_authority():
    paths = (
        Path(
            "services/core/"
            "official_http_transport_v2.py"
        ),
        Path(
            "services/core/"
            "bls_calendar_adapter_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
        "SmartConnect",
        "fyers_apiv3",
        "placeOrder(",
        "place_order",
        "submit_order",
        "BUY_CALL",
        "BUY_PUT",
        "certification_counter",
        "requests.post(",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
