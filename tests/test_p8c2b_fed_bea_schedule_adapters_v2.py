from pathlib import Path
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from services.core.authoritative_event_registry_v2 import (
    new_authoritative_event_registry_v2,
)
from services.core.bea_release_schedule_adapter_v2 import (
    BEA_RELEASE_SCHEDULE_URL,
    BEAReleaseScheduleAdapterV2,
    parse_bea_release_schedule_html,
)
from services.core.federal_reserve_calendar_adapter_v2 import (
    FederalReserveCalendarAdapterV2,
    federal_reserve_month_url,
    parse_federal_reserve_month_calendar_html,
)


OBSERVED_AT = datetime(
    2026,
    9,
    1,
    12,
    0,
    tzinfo=timezone.utc,
)


FED_SEPTEMBER_FIXTURE = """\
<html>
<body>
<h4>September 2026</h4>

<h4>FOMC Meetings</h4>
<h6>Time:</h6>
<h6>Release Date(s):</h6>

<div>2:30 p.m.</div>
<a>FOMC Press Conference</a>
<div>16</div>

<div>2:00 p.m.</div>
<div>FOMC Meeting</div>
<div>Two-day meeting, September 15 - 16</div>
<div>Press Conference</div>
<div>16</div>

<h4>Beige Book</h4>
<div>2:00 p.m.</div>
<div>Beige Book</div>
<div>2</div>
</body>
</html>
"""


FED_OCTOBER_FIXTURE = """\
<html>
<body>
<h4>October 2026</h4>

<h4>FOMC Meetings</h4>

<div>2:00 p.m.</div>
<div>FOMC Minutes</div>
<div>Meeting of September 15-16</div>
<div>7</div>

<div>2:30 p.m.</div>
<div>FOMC Press Conference</div>
<div>28</div>

<div>2:00 p.m.</div>
<div>FOMC Meeting</div>
<div>Two-day meeting, October 27 - 28</div>
<div>Press Conference</div>
<div>28</div>

<h4>Beige Book</h4>
</body>
</html>
"""


BEA_FIXTURE = """\
<html>
<body>
<h1>Release Schedule</h1>
<div>Year 2026</div>

<table>
<tr>
<td>September 24 8:30 AM</td>
<td>News</td>
<td>U.S. International Transactions and Investment Position, 2nd Quarter 2026</td>
</tr>

<tr>
<td>September 30 8:30 AM</td>
<td>News</td>
<td>GDP (Third Estimate), Industries, Corporate Profits, State GDP, and State Personal Income, 2nd Quarter 2026</td>
</tr>

<tr>
<td>September 30 8:30 AM</td>
<td>News</td>
<td>Personal Income and Outlays, August 2026</td>
</tr>

<tr>
<td>October 29 8:30 AM</td>
<td>News</td>
<td>GDP (Advance Estimate), 3rd Quarter 2026</td>
</tr>

<tr>
<td>October 29 8:30 AM</td>
<td>News</td>
<td>Personal Income and Outlays, September 2026</td>
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


def test_fed_september_meeting_parses_exact_eastern_timestamp():
    events = (
        parse_federal_reserve_month_calendar_html(
            FED_SEPTEMBER_FIXTURE,
            year=2026,
            month=9,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(events) == 1

    meeting = events[0]

    assert (
        meeting.event_type
        == "CENTRAL_BANK_POLICY"
    )

    assert meeting.severity == "HIGH"

    assert (
        meeting.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            16,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_fed_october_parses_minutes_and_policy_meeting_separately():
    events = (
        parse_federal_reserve_month_calendar_html(
            FED_OCTOBER_FIXTURE,
            year=2026,
            month=10,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(events) == 2

    by_type = {
        event.event_type:
        event
        for event in events
    }

    assert (
        by_type[
            "CENTRAL_BANK_MINUTES"
        ]
        .scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            10,
            7,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )

    assert (
        by_type[
            "CENTRAL_BANK_POLICY"
        ]
        .scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            10,
            28,
            18,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_fed_press_conference_is_not_double_counted_as_policy_event():
    events = (
        parse_federal_reserve_month_calendar_html(
            FED_SEPTEMBER_FIXTURE,
            year=2026,
            month=9,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert [
        event.title
        for event in events
    ] == [
        "FOMC Meeting",
    ]


def test_fed_adapter_uses_month_specific_official_url():
    transport = FixtureTransport(
        FED_SEPTEMBER_FIXTURE
    )

    adapter = (
        FederalReserveCalendarAdapterV2(
            transport
        )
    )

    events = adapter.fetch_month(
        year=2026,
        month=9,
        observed_at=OBSERVED_AT,
    )

    assert len(events) == 1

    assert (
        transport.calls[0][0]
        == federal_reserve_month_url(
            2026,
            9,
        )
    )


def test_bea_parser_keeps_only_gdp_and_personal_income_outlays():
    events = (
        parse_bea_release_schedule_html(
            BEA_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(events) == 4

    titles = {
        event.title
        for event in events
    }

    assert not any(
        "International Transactions"
        in title
        for title in titles
    )


def test_bea_third_estimate_gdp_is_medium_and_exact_time():
    events = (
        parse_bea_release_schedule_html(
            BEA_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    gdp = next(
        event
        for event in events
        if (
            "Third Estimate"
            in event.title
        )
    )

    assert (
        gdp.event_type
        == "GDP_RELEASE"
    )

    assert gdp.severity == "MEDIUM"

    assert (
        gdp.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            30,
            12,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_bea_advance_gdp_is_high_severity():
    events = (
        parse_bea_release_schedule_html(
            BEA_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    advance = next(
        event
        for event in events
        if (
            "Advance Estimate"
            in event.title
        )
    )

    assert (
        advance.event_type
        == "GDP_RELEASE"
    )

    assert advance.severity == "HIGH"


def test_bea_personal_income_outlays_is_inflation_release():
    events = (
        parse_bea_release_schedule_html(
            BEA_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    pio = [
        event
        for event in events
        if (
            "Personal Income and Outlays"
            in event.title
        )
    ]

    assert len(pio) == 2

    assert all(
        event.event_type
        == "INFLATION_RELEASE"
        for event in pio
    )

    assert all(
        event.severity
        == "HIGH"
        for event in pio
    )


def test_bea_adapter_uses_official_schedule_url():
    transport = FixtureTransport(
        BEA_FIXTURE
    )

    adapter = (
        BEAReleaseScheduleAdapterV2(
            transport
        )
    )

    events = adapter.fetch_events(
        observed_at=OBSERVED_AT,
        year=2026,
    )

    assert len(events) == 4

    assert (
        transport.calls[0][0]
        == BEA_RELEASE_SCHEDULE_URL
    )


def test_fed_and_bea_events_register_in_same_registry():
    registry = (
        new_authoritative_event_registry_v2()
    )

    fed = (
        parse_federal_reserve_month_calendar_html(
            FED_SEPTEMBER_FIXTURE,
            year=2026,
            month=9,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    bea = (
        parse_bea_release_schedule_html(
            BEA_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert (
        registry.register_many(
            fed
        )
        == 1
    )

    assert (
        registry.register_many(
            bea
        )
        == 4
    )


def test_fed_official_event_still_requires_explicit_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    meeting = (
        parse_federal_reserve_month_calendar_html(
            FED_SEPTEMBER_FIXTURE,
            year=2026,
            month=9,
            observed_at=(
                OBSERVED_AT
            ),
        )[0]
    )

    registry.register(
        meeting
    )

    now = (
        meeting.scheduled_at
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
                        "CENTRAL_BANK_POLICY",
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


def test_bea_official_event_still_requires_explicit_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    pio = next(
        event
        for event in (
            parse_bea_release_schedule_html(
                BEA_FIXTURE,
                year=2026,
                observed_at=(
                    OBSERVED_AT
                ),
            )
        )
        if (
            event.event_type
            == "INFLATION_RELEASE"
        )
    )

    registry.register(
        pio
    )

    now = (
        pio.scheduled_at
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


def test_p8c2b_has_no_broker_or_order_authority():
    paths = (
        Path(
            "services/core/"
            "federal_reserve_calendar_adapter_v2.py"
        ),
        Path(
            "services/core/"
            "bea_release_schedule_adapter_v2.py"
        ),
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in paths
    )

    forbidden = (
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
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]
