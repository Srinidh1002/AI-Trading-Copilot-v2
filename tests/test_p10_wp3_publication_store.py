from datetime import datetime, timedelta, timezone

import pytest

from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationStore,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)


NOW = datetime(2026, 7, 30, 13, 0, tzinfo=timezone.utc)


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


def envelope(sequence=1, publication_id=None):
    return DashboardPublicationEnvelopeV1(
        publication_id=publication_id or f"publication-{sequence}",
        publication_sequence=sequence,
        published_at=NOW + timedelta(seconds=sequence),
        source_updated_at=NOW,
        publication_status="READY",
        freshness_status="FRESH",
        opportunity=opportunity(),
        trade_plan=plan(),
    )


def test_store_starts_empty():
    snapshot = DashboardPublicationStore().get_snapshot()

    assert snapshot.latest_envelope is None
    assert snapshot.last_attempt_status == "NOT_ATTEMPTED"


def test_publish_replaces_last_known_good_atomically():
    store = DashboardPublicationStore()
    value = envelope()

    snapshot = store.publish(
        value,
        attempted_at=NOW + timedelta(seconds=2),
    )

    assert snapshot.latest_envelope is value
    assert snapshot.last_attempt_status == "PUBLISHED"
    assert snapshot.publication_count == 1


def test_newer_sequence_replaces_previous_publication():
    store = DashboardPublicationStore()
    store.publish(
        envelope(1),
        attempted_at=NOW + timedelta(seconds=2),
    )

    snapshot = store.publish(
        envelope(2),
        attempted_at=NOW + timedelta(seconds=3),
    )

    assert snapshot.latest_envelope.publication_sequence == 2
    assert snapshot.publication_count == 2


def test_equivalent_duplicate_preserves_semantic_state():
    store = DashboardPublicationStore()
    value = envelope(1)
    store.publish(value, attempted_at=NOW + timedelta(seconds=2))

    snapshot = store.publish(
        value,
        attempted_at=NOW + timedelta(seconds=3),
    )

    assert snapshot.latest_envelope is value
    assert snapshot.last_attempt_status == "DUPLICATE_NO_CHANGE"
    assert snapshot.publication_count == 1


def test_same_sequence_with_different_content_is_rejected():
    store = DashboardPublicationStore()
    store.publish(
        envelope(1),
        attempted_at=NOW + timedelta(seconds=2),
    )

    with pytest.raises(ValueError, match="different content"):
        store.publish(
            envelope(1, publication_id="different"),
            attempted_at=NOW + timedelta(seconds=3),
        )


def test_older_sequence_is_rejected():
    store = DashboardPublicationStore()
    store.publish(
        envelope(2),
        attempted_at=NOW + timedelta(seconds=3),
    )

    with pytest.raises(ValueError, match="cannot move backwards"):
        store.publish(
            envelope(1),
            attempted_at=NOW + timedelta(seconds=4),
        )


def test_failure_preserves_last_known_good():
    store = DashboardPublicationStore()
    value = envelope(1)
    store.publish(value, attempted_at=NOW + timedelta(seconds=2))

    snapshot = store.record_failure(
        attempted_at=NOW + timedelta(seconds=3),
        error=RuntimeError("projection failed"),
    )

    assert snapshot.latest_envelope is value
    assert snapshot.publication_count == 1
    assert snapshot.failed_attempt_count == 1
    assert snapshot.last_attempt_error == "projection failed"


def test_failure_before_first_publication_is_valid():
    snapshot = DashboardPublicationStore().record_failure(
        attempted_at=NOW,
        error="runtime unavailable",
    )

    assert snapshot.latest_envelope is None
    assert snapshot.publication_count == 0
    assert snapshot.failed_attempt_count == 1


def test_reset_is_explicit_and_preserves_failure_count():
    store = DashboardPublicationStore()
    store.record_failure(attempted_at=NOW, error="failure")

    snapshot = store.reset(
        attempted_at=NOW + timedelta(seconds=1),
    )

    assert snapshot.latest_envelope is None
    assert snapshot.last_attempt_status == "RESET"
    assert snapshot.failed_attempt_count == 1


def test_store_rejects_untyped_envelope():
    with pytest.raises(TypeError, match="exact"):
        DashboardPublicationStore().publish(
            object(),
            attempted_at=NOW,
        )
