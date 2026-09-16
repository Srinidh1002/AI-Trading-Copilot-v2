from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

from services.contracts.authoritative_event_v2 import (
    AuthoritativeMarketEventV2,
)
from services.core.authoritative_event_registry_v2 import (
    classify_authoritative_event_phase,
    new_authoritative_event_registry_v2,
)
from services.core.authoritative_event_source_catalog_v2 import (
    AUTHORITATIVE_EVENT_SOURCES,
    get_authoritative_event_source,
)


NOW = datetime(
    2026,
    9,
    16,
    6,
    0,
    tzinfo=timezone.utc,
)


def event(
    *,
    event_id="fed-2026-09",
    event_group_id="fomc-2026-09",
    source_id="FEDERAL_RESERVE",
    event_type="CENTRAL_BANK_POLICY",
    severity="HIGH",
    markets=(
        "NIFTY",
        "SENSEX",
        "GOLDM",
    ),
    scheduled=True,
    scheduled_at=None,
    published_at=None,
):
    if (
        scheduled
        and scheduled_at is None
    ):
        scheduled_at = (
            NOW
            + timedelta(
                minutes=5
            )
        )

    return AuthoritativeMarketEventV2(
        event_id=event_id,
        event_group_id=event_group_id,
        source_id=source_id,
        source_event_id=None,
        title="FOMC policy decision",
        event_type=event_type,
        severity=severity,
        jurisdiction="US",
        affected_markets=markets,
        affected_symbols=(),
        observed_at=NOW,
        scheduled=scheduled,
        scheduled_at=scheduled_at,
        published_at=published_at,
        effective_at=None,
        source_url=(
            "https://www.federalreserve.gov/"
            "monetarypolicy/fomccalendars.htm"
        ),
    )


def test_primary_source_catalog_contains_required_authorities():
    ids = {
        source.source_id
        for source in AUTHORITATIVE_EVENT_SOURCES
    }

    required = {
        "RBI",
        "MOSPI",
        "SEBI",
        "NSE",
        "BSE",
        "MCX",
        "FEDERAL_RESERVE",
        "BLS",
        "BEA",
        "EIA",
        "CFTC",
        "OPEC",
        "IEA",
        "DGFT",
        "CBIC",
        "PIB",
    }

    assert (
        required
        <= ids
    )


def test_all_catalog_sources_are_authoritative_https_sources():
    for source in AUTHORITATIVE_EVENT_SOURCES:
        assert (
            source.authoritative
            is True
        )

        assert (
            source.official_url
            .startswith(
                "https://"
            )
        )


def test_source_market_scope_is_canonical():
    assert (
        get_authoritative_event_source(
            "MCX"
        ).default_markets
        == (
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        )
    )

    assert (
        get_authoritative_event_source(
            "NSE"
        ).default_markets
        == (
            "NIFTY",
        )
    )


def test_scheduled_event_requires_timezone_aware_timestamp():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        event(
            scheduled_at=datetime(
                2026,
                9,
                16,
                18,
                0,
            ),
        )


def test_unscheduled_event_cannot_carry_scheduled_timestamp():
    with pytest.raises(
        ValueError,
        match="Unscheduled",
    ):
        event(
            scheduled=False,
            scheduled_at=NOW,
        )


def test_event_markets_are_canonicalized():
    item = event(
        markets=(
            "NIFTY 50",
            "BSE SENSEX",
            "GOLD MINI",
        )
    )

    assert (
        item.affected_markets
        == (
            "NIFTY",
            "SENSEX",
            "GOLDM",
        )
    )


def test_registry_rejects_source_event_type_mismatch():
    registry = (
        new_authoritative_event_registry_v2()
    )

    bad = event(
        source_id="EIA",
        event_type="COMPANY_DISCLOSURE",
        markets=(
            "CRUDEOILM",
        ),
    )

    with pytest.raises(
        ValueError,
        match="not supported",
    ):
        registry.register(
            bad
        )


def test_registry_registration_is_idempotent_for_identical_event():
    registry = (
        new_authoritative_event_registry_v2()
    )

    item = event()

    assert (
        registry.register(
            item
        )
        is True
    )

    assert (
        registry.register(
            item
        )
        is False
    )


def test_event_lifecycle_uses_scheduled_and_published_evidence():
    item = event(
        scheduled_at=(
            NOW
            + timedelta(
                minutes=5
            )
        )
    )

    assert (
        classify_authoritative_event_phase(
            item,
            NOW,
        )
        == "IMMINENT"
    )

    late = (
        NOW
        + timedelta(
            minutes=7
        )
    )

    assert (
        classify_authoritative_event_phase(
            item,
            late,
        )
        == "AWAITING_RELEASE"
    )

    released = event(
        scheduled_at=(
            NOW
            - timedelta(
                minutes=1
            )
        ),
        published_at=NOW,
    )

    assert (
        classify_authoritative_event_phase(
            released,
            NOW,
        )
        == "RELEASED"
    )


def test_authoritative_source_does_not_automatically_hard_block():
    registry = (
        new_authoritative_event_registry_v2()
    )

    registry.register(
        event()
    )

    payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=NOW,
        )
    )

    assert (
        payload[
            "source_authoritative"
        ]
        is True
    )

    assert (
        payload[
            "block_entries"
        ]
        is False
    )

    assert (
        payload[
            "policy_event_types"
        ]
        == ()
    )


def test_explicit_policy_can_make_authoritative_high_event_block_candidate():
    registry = (
        new_authoritative_event_registry_v2()
    )

    registry.register(
        event()
    )

    payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=NOW,
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
        payload[
            "block_entries"
        ]
        is True
    )

    assert (
        payload[
            "events"
        ][0][
            "policy_block_candidate"
        ]
        is True
    )


def test_medium_severity_event_does_not_hard_block_by_default_severity_policy():
    registry = (
        new_authoritative_event_registry_v2()
    )

    registry.register(
        event(
            severity="MEDIUM"
        )
    )

    payload = (
        registry
        .build_event_risk_payload(
            market_symbol="NIFTY",
            now=NOW,
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
        payload[
            "block_entries"
        ]
        is False
    )


def test_duplicate_group_collapses_for_risk_view():
    registry = (
        new_authoritative_event_registry_v2()
    )

    first = event(
        event_id="fed-calendar",
        event_group_id="fomc-2026-09",
    )

    second = AuthoritativeMarketEventV2(
        event_id="fed-statement",
        event_group_id="fomc-2026-09",
        source_id="FEDERAL_RESERVE",
        source_event_id=None,
        title="FOMC statement",
        event_type="CENTRAL_BANK_POLICY",
        severity="HIGH",
        jurisdiction="US",
        affected_markets=(
            "NIFTY",
            "SENSEX",
            "GOLDM",
        ),
        affected_symbols=(),
        observed_at=(
            NOW
            + timedelta(
                minutes=1
            )
        ),
        scheduled=True,
        scheduled_at=(
            NOW
            + timedelta(
                minutes=5
            )
        ),
        published_at=None,
        effective_at=None,
        source_url=(
            "https://www.federalreserve.gov/"
            "monetarypolicy/fomccalendars.htm"
        ),
    )

    registry.register_many(
        (
            first,
            second,
        )
    )

    assert len(
        registry.list_for_market(
            "NIFTY"
        )
    ) == 2

    assert len(
        registry.unique_for_market(
            "NIFTY"
        )
    ) == 1


def test_foundation_has_no_network_or_trading_authority():
    paths = (
        Path(
            "services/contracts/"
            "authoritative_event_v2.py"
        ),
        Path(
            "services/core/"
            "authoritative_event_source_catalog_v2.py"
        ),
        Path(
            "services/core/"
            "authoritative_event_registry_v2.py"
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
        "httpx.",
        "aiohttp",
        "BeautifulSoup",
        "SmartConnect",
        "fyers_apiv3",
        "placeOrder(",
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
