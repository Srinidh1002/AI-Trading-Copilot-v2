from datetime import date, datetime, timezone

import pytest

from services.contracts.external_market_observation_v1 import (
    ExternalMarketObservationV1,
)
from services.contracts.institutional_flow_snapshot_v1 import (
    InstitutionalFlowSnapshotV1,
)
from services.contracts.scheduled_market_event_v1 import (
    ScheduledMarketEventV1,
)
from services.paper_orchestration.external_context_source_authority import (
    ExternalContextSourceAuthority,
)


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)


def global_observation():
    return ExternalMarketObservationV1(
        external_market_observation_id="sp500",
        created_at=NOW,
        canonical_name="SP500",
        observation_type="INDEX_CLOSE",
        market_region="UNITED_STATES",
        asset_class="EQUITY_INDEX",
        source_id="GLOBAL_SOURCE",
        source_timestamp=NOW,
        session_reference="PREVIOUS_SESSION_CLOSE",
        current_value=101.0,
        previous_value=100.0,
        change_value=1.0,
        change_percent=1.0,
        direction="POSITIVE",
        observation_status="READY",
    )


def institutional_snapshot():
    return InstitutionalFlowSnapshotV1(
        institutional_flow_snapshot_id="flows",
        created_at=NOW,
        trading_date=date(2026, 8, 3),
        source_id="INSTITUTIONAL_SOURCE",
        source_timestamp=NOW,
        publication_state="FINAL",
        session_reference="END_OF_DAY",
        currency="INR",
        cash_flow_unit="CRORE_INR",
        derivatives_position_unit="CONTRACTS",
        fii_cash_net=500.0,
        dii_cash_net=250.0,
        fii_index_futures_net=1500.0,
        fii_index_options_net=1200.0,
        flow_status="READY",
    )


def scheduled_event():
    return ScheduledMarketEventV1(
        scheduled_market_event_id="expiry",
        created_at=NOW,
        event_name="NIFTY Weekly Expiry",
        event_category="WEEKLY_EXPIRY",
        scheduled_start=NOW,
        scheduled_end=None,
        source_id="EVENT_SOURCE",
        source_timestamp=NOW,
        confirmation_state="CONFIRMED",
        event_status="ACTIVE",
        severity="MODERATE",
        affected_market_identities=(("NIFTY", "NSE"),),
        affected_exchanges=("NSE",),
        analysis_allowed=True,
        new_entries_allowed=True,
        session_override_state="NONE",
    )


def test_authority_reads_each_source_once_and_reuses_capture():
    calls = {"global": 0, "institutional": 0, "event": 0}

    def global_reader(evaluated_at):
        calls["global"] += 1
        assert evaluated_at == NOW
        return (global_observation(),)

    def institutional_reader(evaluated_at):
        calls["institutional"] += 1
        assert evaluated_at == NOW
        return institutional_snapshot()

    def event_reader(evaluated_at):
        calls["event"] += 1
        assert evaluated_at == NOW
        return ()

    authority = ExternalContextSourceAuthority(
        global_reader=global_reader,
        institutional_reader=institutional_reader,
        event_reader=event_reader,
    )

    first = authority.build(
        cycle_id="parent-cycle",
        evaluated_at=NOW,
    )
    second = authority.build(
        cycle_id="parent-cycle",
        evaluated_at=NOW,
    )

    assert first is second
    assert calls == {
        "global": 1,
        "institutional": 1,
        "event": 1,
    }
    assert authority.build_count == 1
    assert authority.global_provider_call_count == 1
    assert authority.institutional_provider_call_count == 1
    assert authority.event_provider_call_count == 1
    assert first.nifty.global_context is not None
    assert first.sensex.global_context is not None
    assert first.nifty.institutional_context is not None
    assert first.sensex.institutional_context is not None


def test_missing_sources_remain_explicitly_unavailable():
    authority = ExternalContextSourceAuthority()
    result = authority.build(
        cycle_id="parent-cycle",
        evaluated_at=NOW,
    )

    assert result.nifty.context_status == "UNAVAILABLE"
    assert result.sensex.context_status == "UNAVAILABLE"
    assert authority.build_count == 1
    assert authority.global_provider_call_count == 0
    assert authority.institutional_provider_call_count == 0
    assert authority.event_provider_call_count == 0


def test_invalid_source_outputs_fail_closed():
    authority = ExternalContextSourceAuthority(
        global_reader=lambda _: ({},),
    )
    with pytest.raises(TypeError):
        authority.build(
            cycle_id="parent-cycle",
            evaluated_at=NOW,
        )

    authority = ExternalContextSourceAuthority(
        institutional_reader=lambda _: {},
    )
    with pytest.raises(TypeError):
        authority.build(
            cycle_id="parent-cycle",
            evaluated_at=NOW,
        )

    authority = ExternalContextSourceAuthority(
        event_reader=lambda _: ({},),
    )
    with pytest.raises(TypeError):
        authority.build(
            cycle_id="parent-cycle",
            evaluated_at=NOW,
        )


def test_duplicate_global_and_event_records_are_rejected():
    observation = global_observation()
    authority = ExternalContextSourceAuthority(
        global_reader=lambda _: (observation, observation),
    )
    with pytest.raises(ValueError):
        authority.build(
            cycle_id="parent-cycle",
            evaluated_at=NOW,
        )

    event = scheduled_event()
    authority = ExternalContextSourceAuthority(
        event_reader=lambda _: (event, event),
    )
    with pytest.raises(ValueError):
        authority.build(
            cycle_id="parent-cycle",
            evaluated_at=NOW,
        )


def test_reader_dependencies_must_be_callable():
    with pytest.raises(TypeError):
        ExternalContextSourceAuthority(global_reader=object())
    with pytest.raises(TypeError):
        ExternalContextSourceAuthority(
            institutional_reader=object()
        )
    with pytest.raises(TypeError):
        ExternalContextSourceAuthority(event_reader=object())
