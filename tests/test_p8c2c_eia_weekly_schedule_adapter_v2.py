from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from services.core.authoritative_event_registry_v2 import (
    new_authoritative_event_registry_v2,
)
from services.core.eia_weekly_schedule_adapter_v2 import (
    EIA_NATURAL_GAS_SCHEDULE_URL,
    EIA_PETROLEUM_SCHEDULE_URL,
    EIAWeeklyScheduleAdapterV2,
    build_eia_natural_gas_schedule,
    build_eia_petroleum_schedule,
)


OBSERVED_AT = datetime(
    2026,
    9,
    1,
    12,
    0,
    tzinfo=timezone.utc,
)


PETROLEUM_FIXTURE = """\
<html>
<body>
<h1>Weekly Petroleum Status Report Schedule</h1>
<p>
The standard release time and day of the week will be
at 10:30 a.m. eastern time on Wednesdays with the
following exceptions.
</p>

<table>
<tr>
<th>Data for the week ending</th>
<th>Alternate release date</th>
<th>Release day</th>
<th>Release time</th>
<th>Holiday</th>
</tr>

<tr>
<td>January 16, 2026</td>
<td>January 22, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>Martin Luther King Jr. Day</td>
</tr>

<tr>
<td>February 13, 2026</td>
<td>February 19, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>President's Day</td>
</tr>

<tr>
<td>May 22, 2026</td>
<td>May 28, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>Memorial Day</td>
</tr>

<tr>
<td>September 4, 2026</td>
<td>September 10, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>Labor Day</td>
</tr>

<tr>
<td>October 9, 2026</td>
<td>October 15, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>Columbus Day</td>
</tr>

<tr>
<td>November 6, 2026</td>
<td>November 12, 2026</td>
<td>Thursday</td>
<td>12:00 p.m.</td>
<td>Veterans Day</td>
</tr>
</table>
</body>
</html>
"""


NATGAS_FIXTURE = """\
<html>
<body>
<h1>Weekly Natural Gas Storage Report Schedule</h1>

<p>
The standard release time and day of the week will be
at 10:30 a.m. eastern time on Thursdays with the
following exceptions.
</p>

<table>
<tr>
<th>Alternate release date</th>
<th>Release day</th>
<th>Release time</th>
<th>Holiday</th>
</tr>

<tr>
<td>November 13, 2026</td>
<td>Friday</td>
<td>10:30 a.m.</td>
<td>Veterans Day</td>
</tr>

<tr>
<td>November 25, 2026</td>
<td>Wednesday</td>
<td>12:00 p.m.</td>
<td>Thanksgiving Day</td>
</tr>
</table>
</body>
</html>
"""


class FixtureTransport:
    def __init__(
        self,
        payload_by_url,
    ):
        self.payload_by_url = dict(
            payload_by_url
        )

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

        return self.payload_by_url[
            url
        ]


def _by_date(
    events,
):
    return {
        event.scheduled_at.date():
        event
        for event in events
    }


def test_petroleum_standard_week_is_wednesday_1030_eastern():
    events = (
        build_eia_petroleum_schedule(
            PETROLEUM_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    event = by_date[
        datetime(
            2026,
            9,
            2,
        ).date()
    ]

    assert (
        event.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            2,
            14,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_petroleum_labor_day_override_replaces_standard_wednesday():
    events = (
        build_eia_petroleum_schedule(
            PETROLEUM_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    assert (
        datetime(
            2026,
            9,
            9,
        ).date()
        not in by_date
    )

    alternate = by_date[
        datetime(
            2026,
            9,
            10,
        ).date()
    ]

    assert (
        alternate.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            10,
            16,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_petroleum_october_and_november_2026_overrides_are_applied():
    events = (
        build_eia_petroleum_schedule(
            PETROLEUM_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    assert (
        datetime(
            2026,
            10,
            14,
        ).date()
        not in by_date
    )

    assert (
        datetime(
            2026,
            10,
            15,
        ).date()
        in by_date
    )

    assert (
        datetime(
            2026,
            11,
            11,
        ).date()
        not in by_date
    )

    assert (
        datetime(
            2026,
            11,
            12,
        ).date()
        in by_date
    )


def test_petroleum_events_are_crude_only_inventory_events():
    events = (
        build_eia_petroleum_schedule(
            PETROLEUM_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert all(
        event.event_type
        == "COMMODITY_INVENTORY"
        for event in events
    )

    assert all(
        event.severity
        == "HIGH"
        for event in events
    )

    assert all(
        event.affected_markets
        == (
            "CRUDEOILM",
        )
        for event in events
    )


def test_natural_gas_standard_week_is_thursday_1030_eastern():
    events = (
        build_eia_natural_gas_schedule(
            NATGAS_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    event = by_date[
        datetime(
            2026,
            9,
            17,
        ).date()
    ]

    assert (
        event.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            9,
            17,
            14,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_natural_gas_veterans_day_override_replaces_thursday():
    events = (
        build_eia_natural_gas_schedule(
            NATGAS_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    assert (
        datetime(
            2026,
            11,
            12,
        ).date()
        not in by_date
    )

    alternate = by_date[
        datetime(
            2026,
            11,
            13,
        ).date()
    ]

    assert (
        alternate.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            11,
            13,
            15,
            30,
            tzinfo=timezone.utc,
        )
    )


def test_natural_gas_thanksgiving_override_is_wednesday_noon():
    events = (
        build_eia_natural_gas_schedule(
            NATGAS_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    by_date = _by_date(
        events
    )

    assert (
        datetime(
            2026,
            11,
            26,
        ).date()
        not in by_date
    )

    alternate = by_date[
        datetime(
            2026,
            11,
            25,
        ).date()
    ]

    assert (
        alternate.scheduled_at
        .astimezone(
            timezone.utc
        )
        == datetime(
            2026,
            11,
            25,
            17,
            0,
            tzinfo=timezone.utc,
        )
    )


def test_natural_gas_events_are_natgas_only_storage_events():
    events = (
        build_eia_natural_gas_schedule(
            NATGAS_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert all(
        event.event_type
        == "NATGAS_STORAGE"
        for event in events
    )

    assert all(
        event.severity
        == "HIGH"
        for event in events
    )

    assert all(
        event.affected_markets
        == (
            "NATGASMINI",
        )
        for event in events
    )


def test_eia_events_register_in_authoritative_registry():
    registry = (
        new_authoritative_event_registry_v2()
    )

    petroleum = (
        build_eia_petroleum_schedule(
            PETROLEUM_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    natural_gas = (
        build_eia_natural_gas_schedule(
            NATGAS_FIXTURE,
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert (
        registry.register_many(
            petroleum
        )
        == len(
            petroleum
        )
    )

    assert (
        registry.register_many(
            natural_gas
        )
        == len(
            natural_gas
        )
    )


def test_eia_inventory_event_requires_explicit_block_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    event = next(
        event
        for event in (
            build_eia_petroleum_schedule(
                PETROLEUM_FIXTURE,
                year=2026,
                observed_at=(
                    OBSERVED_AT
                ),
            )
        )
        if (
            event.scheduled_at.date()
            == datetime(
                2026,
                9,
                2,
            ).date()
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
            market_symbol="CRUDEOILM",
            now=now,
        )
    )

    policy_payload = (
        registry
        .build_event_risk_payload(
            market_symbol="CRUDEOILM",
            now=now,
            hard_block_event_types=(
                frozenset(
                    {
                        "COMMODITY_INVENTORY",
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


def test_eia_natgas_event_requires_explicit_block_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    event = next(
        event
        for event in (
            build_eia_natural_gas_schedule(
                NATGAS_FIXTURE,
                year=2026,
                observed_at=(
                    OBSERVED_AT
                ),
            )
        )
        if (
            event.scheduled_at.date()
            == datetime(
                2026,
                9,
                17,
            ).date()
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
            market_symbol="NATGASMINI",
            now=now,
        )
    )

    policy_payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NATGASMINI",
            now=now,
            hard_block_event_types=(
                frozenset(
                    {
                        "NATGAS_STORAGE",
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


def test_adapter_uses_both_official_eia_schedule_urls():
    transport = FixtureTransport(
        {
            EIA_PETROLEUM_SCHEDULE_URL:
            PETROLEUM_FIXTURE,

            EIA_NATURAL_GAS_SCHEDULE_URL:
            NATGAS_FIXTURE,
        }
    )

    adapter = (
        EIAWeeklyScheduleAdapterV2(
            transport
        )
    )

    petroleum = (
        adapter.fetch_petroleum(
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    gas = (
        adapter.fetch_natural_gas(
            year=2026,
            observed_at=(
                OBSERVED_AT
            ),
        )
    )

    assert petroleum
    assert gas

    called_urls = {
        value[0]
        for value in transport.calls
    }

    assert (
        EIA_PETROLEUM_SCHEDULE_URL
        in called_urls
    )

    assert (
        EIA_NATURAL_GAS_SCHEDULE_URL
        in called_urls
    )


def test_eia_adapter_has_no_broker_or_order_authority():
    path = Path(
        "services/core/"
        "eia_weekly_schedule_adapter_v2.py"
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
