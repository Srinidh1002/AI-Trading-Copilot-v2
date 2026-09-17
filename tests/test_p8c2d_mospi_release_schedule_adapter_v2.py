from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from services.core.authoritative_event_registry_v2 import (
    new_authoritative_event_registry_v2,
)
from services.core.mospi_release_schedule_adapter_v2 import (
    MOSPI_RELEASE_CALENDAR_URL,
    MoSPIReleaseScheduleAdapterV2,
    parse_mospi_release_calendar_html,
)


OBSERVED_AT = datetime(
    2026,
    9,
    16,
    12,
    0,
    tzinfo=timezone.utc,
)


MOSPI_FIXTURE = """\
<html>
<body>
<table>
<tr>
<th>S.no</th>
<th>Month</th>
<th>Date of release</th>
<th>Data Release / Publication</th>
</tr>

<tr>
<td>8</td>
<td>Nov 2026</td>
<td>28th Nov</td>
<td>All India Index of Industrial Production (IIP)</td>
</tr>

<tr>
<td></td>
<td></td>
<td>30th Nov</td>
<td>Quarterly Estimates of GDP for Q2, FY 2026-27</td>
</tr>

<tr>
<td>9</td>
<td>Dec 2026</td>
<td>12th Dec</td>
<td>All India Consumer Price Index (CPI)</td>
</tr>

<tr>
<td></td>
<td></td>
<td>15th Dec</td>
<td>Monthly Bulletin of PLFS - Nov 2026</td>
</tr>

<tr>
<td></td>
<td></td>
<td>28th Dec</td>
<td>All India Index of Industrial Production (IIP)</td>
</tr>

<tr>
<td>10</td>
<td>Jan 2027</td>
<td>7thJan</td>
<td>First Advance Estimates of GDP for FY 2026-27</td>
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


def _events():
    return (
        parse_mospi_release_calendar_html(
            MOSPI_FIXTURE,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )


def test_mospi_parser_keeps_cpi_iip_and_gdp_only():
    events = _events()

    assert len(
        events
    ) == 5

    assert not any(
        "PLFS"
        in event.title
        for event in events
    )


def test_mospi_iip_is_1600_india_time():
    event = next(
        event
        for event in _events()
        if (
            event.event_type
            == "INDUSTRIAL_PRODUCTION"
        )
        and (
            event.scheduled_at.month
            == 11
        )
    )

    assert (
        event.severity
        == "MEDIUM"
    )

    assert (
        event.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            11,
            28,
            10,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_mospi_gdp_is_1600_india_time():
    event = next(
        event
        for event in _events()
        if (
            event.event_type
            == "GDP_RELEASE"
        )
        and (
            event.scheduled_at.month
            == 11
        )
    )

    assert (
        event.severity
        == "HIGH"
    )

    assert (
        event.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            11,
            30,
            10,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_mospi_cpi_is_1730_india_time():
    event = next(
        event
        for event in _events()
        if (
            event.event_type
            == "INFLATION_RELEASE"
        )
    )

    assert (
        event.severity
        == "HIGH"
    )

    assert (
        event.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            12,
            12,
            12,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_mospi_parser_handles_calendar_year_rollover():
    event = next(
        event
        for event in _events()
        if (
            event.scheduled_at.year
            == 2027
        )
    )

    assert (
        event.event_type
        == "GDP_RELEASE"
    )

    assert (
        event.scheduled_at.month
        == 1
    )

    assert (
        event.scheduled_at.day
        == 7
    )


def test_mospi_events_use_india_macro_market_scope():
    events = _events()

    assert all(
        event.affected_markets
        == (
            "NIFTY",
            "SENSEX",
            "GOLDM",
        )
        for event in events
    )


def test_plfs_is_not_given_an_invented_intraday_time():
    events = _events()

    assert not [
        event
        for event in events
        if "PLFS"
        in event.title
    ]


def test_empty_dynamic_calendar_fails_closed_to_no_events():
    html = """\
    <html>
      <body>
        <h1>Release Calendar</h1>
        <p>0 releases</p>
      </body>
    </html>
    """

    events = (
        parse_mospi_release_calendar_html(
            html,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert events == ()


def test_mospi_event_requires_explicit_block_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    event = next(
        event
        for event in _events()
        if (
            event.event_type
            == "GDP_RELEASE"
        )
    )

    registry.register(
        event
    )

    now = (
        event.scheduled_at
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
                        "GDP_RELEASE",
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


def test_mospi_adapter_uses_official_release_calendar():
    transport = (
        FixtureTransport(
            MOSPI_FIXTURE
        )
    )

    adapter = (
        MoSPIReleaseScheduleAdapterV2(
            transport
        )
    )

    events = (
        adapter.fetch_events(
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert len(
        events
    ) == 5

    assert (
        transport.calls[0][0]
        == MOSPI_RELEASE_CALENDAR_URL
    )


def test_parser_is_stable_for_same_calendar_payload():
    first = _events()

    second = _events()

    assert [
        event.event_id
        for event in first
    ] == [
        event.event_id
        for event in second
    ]


def test_mospi_adapter_has_no_broker_or_order_authority():
    path = Path(
        "services/core/"
        "mospi_release_schedule_adapter_v2.py"
    )

    text = path.read_text(
        encoding="utf-8",
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
