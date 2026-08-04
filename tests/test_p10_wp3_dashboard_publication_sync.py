from datetime import datetime, timedelta, timezone

import pytest

from dashboard.dashboard_publication_sync import (
    PUBLICATION_ATTEMPT_ERROR_STATE_KEY,
    PUBLICATION_ATTEMPT_STATUS_STATE_KEY,
    PUBLICATION_FAILED_ATTEMPT_COUNT_STATE_KEY,
    PUBLICATION_FRESHNESS_STATE_KEY,
    PUBLICATION_ID_STATE_KEY,
    PUBLICATION_PUBLISHED_AT_STATE_KEY,
    PUBLICATION_SEQUENCE_STATE_KEY,
    PUBLICATION_SOURCE_UPDATED_AT_STATE_KEY,
    PUBLICATION_STATUS_STATE_KEY,
    synchronize_dashboard_publication,
)
from dashboard.dashboard_read_model_state import (
    OPPORTUNITY_STATE_KEY,
    PAPER_POSITION_STATE_KEY,
    TRADE_PLAN_STATE_KEY,
)
from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc)


def opportunity():
    return DashboardOpportunityViewV1(
        opportunity_id="opportunity-1",
        created_at=NOW,
        snapshot_id="snapshot-1",
        decision_id="decision-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        opportunity_status="READY",
        action="BUY",
        directional_bias="BULLISH",
        option_type="CALL",
        contract_id="contract-1",
        trading_symbol="NIFTY-CE",
        instrument_token="token-1",
        strike=25000,
        expiry=None,
        lot_size=75,
        reference_option_price=100,
        technical_strength=0.8,
        option_chain_strength=0.7,
        contract_ranking_score=0.9,
        decision_confidence=0.85,
        opportunity_score=0.82,
    )


def plan():
    targets = tuple(
        DashboardTradePlanTargetViewV1(
            target_name=f"T{number}",
            target_price=100 + number * 20,
        )
        for number in (1, 2, 3)
    )
    return DashboardTradePlanViewV1(
        trade_plan_id="plan-1",
        selected_opportunity_id="opportunity-1",
        evaluated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        market="NIFTY",
        plan_status="READY",
        direction="BULLISH",
        instrument_type="INDEX_OPTION",
        opportunity_confidence=0.8,
        option_confidence=0.75,
        plan_confidence=0.78,
        targets=targets,
    )


def envelope(sequence=1):
    return DashboardPublicationEnvelopeV1(
        publication_id=f"publication-{sequence}",
        publication_sequence=sequence,
        published_at=NOW + timedelta(seconds=sequence),
        source_updated_at=NOW,
        publication_status="READY",
        freshness_status="FRESH",
        opportunity=opportunity(),
        trade_plan=plan(),
    )


def snapshot(sequence=1):
    value = envelope(sequence)
    return DashboardPublicationSnapshotV1(
        latest_envelope=value,
        last_successful_publication_at=value.published_at,
        last_attempted_publication_at=value.published_at,
        last_attempt_status="PUBLISHED",
        last_attempt_error=None,
        publication_count=sequence,
        failed_attempt_count=0,
    )


def test_newer_publication_is_copied_into_state():
    state = {}

    changed = synchronize_dashboard_publication(state, snapshot(1))

    assert changed is True
    assert state[OPPORTUNITY_STATE_KEY].opportunity_id == "opportunity-1"
    assert state[TRADE_PLAN_STATE_KEY].trade_plan_id == "plan-1"
    assert state[PAPER_POSITION_STATE_KEY] is None
    assert state[PUBLICATION_ID_STATE_KEY] == "publication-1"
    assert state[PUBLICATION_SEQUENCE_STATE_KEY] == 1
    assert state[PUBLICATION_STATUS_STATE_KEY] == "READY"
    assert state[PUBLICATION_FRESHNESS_STATE_KEY] == "FRESH"
    assert state[PUBLICATION_PUBLISHED_AT_STATE_KEY] == NOW + timedelta(seconds=1)
    assert state[PUBLICATION_SOURCE_UPDATED_AT_STATE_KEY] == NOW


def test_same_or_older_sequence_does_not_replace_state():
    state = {}
    synchronize_dashboard_publication(state, snapshot(2))
    original_plan = state[TRADE_PLAN_STATE_KEY]

    assert synchronize_dashboard_publication(state, snapshot(2)) is False
    assert synchronize_dashboard_publication(state, snapshot(1)) is False
    assert state[TRADE_PLAN_STATE_KEY] is original_plan
    assert state[PUBLICATION_SEQUENCE_STATE_KEY] == 2


def test_empty_snapshot_does_not_clear_existing_views():
    state = {
        OPPORTUNITY_STATE_KEY: opportunity(),
        TRADE_PLAN_STATE_KEY: plan(),
        PAPER_POSITION_STATE_KEY: None,
        PUBLICATION_SEQUENCE_STATE_KEY: 5,
    }

    changed = synchronize_dashboard_publication(
        state,
        DashboardPublicationSnapshotV1.empty(),
    )

    assert changed is False
    assert state[OPPORTUNITY_STATE_KEY] is not None
    assert state[TRADE_PLAN_STATE_KEY] is not None
    assert state[PUBLICATION_SEQUENCE_STATE_KEY] == 5


def test_failed_attempt_metadata_updates_without_clearing_views():
    good = snapshot(1)
    failed = DashboardPublicationSnapshotV1(
        latest_envelope=good.latest_envelope,
        last_successful_publication_at=good.last_successful_publication_at,
        last_attempted_publication_at=NOW + timedelta(seconds=10),
        last_attempt_status="FAILED_ATTEMPT_PRESERVED",
        last_attempt_error="projection failed",
        publication_count=1,
        failed_attempt_count=3,
    )
    state = {}
    synchronize_dashboard_publication(state, good)

    changed = synchronize_dashboard_publication(state, failed)

    assert changed is False
    assert state[TRADE_PLAN_STATE_KEY].trade_plan_id == "plan-1"
    assert (
        state[PUBLICATION_ATTEMPT_STATUS_STATE_KEY]
        == "FAILED_ATTEMPT_PRESERVED"
    )
    assert (
        state[PUBLICATION_ATTEMPT_ERROR_STATE_KEY]
        == "projection failed"
    )
    assert state[PUBLICATION_FAILED_ATTEMPT_COUNT_STATE_KEY] == 3


def test_sync_rejects_nonmutable_state():
    with pytest.raises(TypeError, match="mutable mapping"):
        synchronize_dashboard_publication((), snapshot())


def test_sync_rejects_untyped_snapshot():
    with pytest.raises(TypeError, match="exact"):
        synchronize_dashboard_publication({}, object())


def test_corrupt_existing_sequence_is_rejected():
    state = {PUBLICATION_SEQUENCE_STATE_KEY: "1"}

    with pytest.raises(TypeError, match="exact int"):
        synchronize_dashboard_publication(state, snapshot(2))
