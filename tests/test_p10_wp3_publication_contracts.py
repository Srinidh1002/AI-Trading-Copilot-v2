from datetime import datetime, timedelta, timezone

import pytest

from services.dashboard_publication import (
    DashboardPublicationEnvelopeV1,
    DashboardPublicationSnapshotV1,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanViewV1,
)
from services.dashboard_read_models import (
    DashboardOpportunityViewV1,
    DashboardPaperPositionDetailViewV1,
    DashboardTradePlanTargetViewV1,
    DashboardTradePlanViewV1,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


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
    targets = (
        DashboardTradePlanTargetViewV1(
            target_name="T1",
            target_price=120.0,
            reward_to_risk=1.0,
            booking_fraction=0.5,
        ),
        DashboardTradePlanTargetViewV1(
            target_name="T2",
            target_price=140.0,
            reward_to_risk=2.0,
            booking_fraction=0.3,
        ),
        DashboardTradePlanTargetViewV1(
            target_name="T3",
            target_price=160.0,
            reward_to_risk=3.0,
            booking_fraction=0.2,
        ),
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


def position():
    return DashboardPaperPositionDetailViewV1(
        paper_trade_id="paper-trade-1",
        position_id=None,
        trade_plan_id="plan-1",
        integrated_trade_plan_result_id="integrated-1",
        lifecycle_state_id="lifecycle-1",
        lifecycle_state="WAITING_FOR_ENTRY",
        lifecycle_display_group="PENDING",
        transition_sequence=1,
        is_terminal=False,
        last_transition_code="WAITING_FOR_ENTRY",
        updated_at=NOW,
    )


def envelope(**overrides):
    values = {
        "publication_id": "publication-1",
        "publication_sequence": 1,
        "published_at": NOW,
        "source_updated_at": NOW - timedelta(seconds=1),
        "publication_status": "READY",
        "freshness_status": "FRESH",
        "opportunity": opportunity(),
        "trade_plan": plan(),
        "paper_position": position(),
    }
    values.update(overrides)
    return DashboardPublicationEnvelopeV1(**values)


def test_ready_envelope_is_immutable_and_paper_only():
    value = envelope()

    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.schema_version == "dashboard_publication_envelope.v1"

    with pytest.raises((AttributeError, TypeError)):
        value.publication_id = "changed"


def test_ready_envelope_requires_coherent_opportunity_and_plan():
    with pytest.raises(ValueError, match="requires opportunity and trade_plan"):
        envelope(opportunity=None, trade_plan=None)


def test_plan_requires_opportunity():
    with pytest.raises(ValueError, match="trade_plan requires opportunity"):
        envelope(opportunity=None)


def test_plan_and_position_identity_are_checked():
    bad = DashboardPaperPositionDetailViewV1(
        paper_trade_id="paper-trade-1",
        position_id=None,
        trade_plan_id="different-plan",
        integrated_trade_plan_result_id="integrated-1",
        lifecycle_state_id="lifecycle-1",
        lifecycle_state="WAITING_FOR_ENTRY",
        lifecycle_display_group="PENDING",
        transition_sequence=1,
        is_terminal=False,
        last_transition_code="WAITING_FOR_ENTRY",
        updated_at=NOW,
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        envelope(paper_position=bad)


def test_blocked_publication_requires_blockers():
    with pytest.raises(ValueError, match="requires blockers"):
        envelope(
            publication_status="BLOCKED",
            opportunity=None,
            trade_plan=None,
            paper_position=None,
        )


def test_stale_status_requires_stale_freshness():
    with pytest.raises(ValueError, match="requires STALE freshness"):
        envelope(publication_status="STALE")


def test_diagnostics_are_deduplicated_without_reordering():
    value = envelope(
        warnings=("W1", "W1", "W2"),
        publication_status="READY_WITH_WARNINGS",
    )

    assert value.warnings == ("W1", "W2")


def test_empty_snapshot_is_valid():
    value = DashboardPublicationSnapshotV1.empty()

    assert value.latest_envelope is None
    assert value.last_attempt_status == "NOT_ATTEMPTED"
    assert value.publication_count == 0


def test_published_snapshot_requires_matching_success_time():
    value = envelope()

    snapshot = DashboardPublicationSnapshotV1(
        latest_envelope=value,
        last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW,
        last_attempt_status="PUBLISHED",
        last_attempt_error=None,
        publication_count=1,
        failed_attempt_count=0,
    )

    assert snapshot.latest_envelope is value


def test_failed_attempt_snapshot_preserves_latest_envelope():
    value = envelope()

    snapshot = DashboardPublicationSnapshotV1(
        latest_envelope=value,
        last_successful_publication_at=NOW,
        last_attempted_publication_at=NOW + timedelta(seconds=5),
        last_attempt_status="FAILED_ATTEMPT_PRESERVED",
        last_attempt_error="projection failed",
        publication_count=1,
        failed_attempt_count=1,
    )

    assert snapshot.latest_envelope is value
    assert snapshot.publication_count == 1
    assert snapshot.failed_attempt_count == 1


def test_failed_attempt_requires_error():
    with pytest.raises(ValueError, match="requires last_attempt_error"):
        DashboardPublicationSnapshotV1(
            latest_envelope=None,
            last_successful_publication_at=None,
            last_attempted_publication_at=NOW,
            last_attempt_status="FAILED_ATTEMPT_PRESERVED",
            last_attempt_error=None,
            publication_count=0,
            failed_attempt_count=1,
        )
