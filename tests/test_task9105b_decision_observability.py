from datetime import datetime, timezone

import pytest

from services.certification.task9_decision_observability_projector import (
    build_task9_decision_observability,
)
from services.contracts.canonical_directional_policy_v1 import (
    CanonicalDirectionalPolicyV1,
)
from services.contracts.task9_decision_observability_v1 import (
    Task9DecisionObservabilityV1,
    Task9ProviderParticipationV1,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
)


NOW = datetime(
    2026,
    8,
    25,
    10,
    0,
    tzinfo=timezone.utc,
)


def _audit(
    *,
    blocker="REGIME_BLOCKED",
    planner=False,
    entry=False,
):
    return Task9LiveDecisionAuditV1(
        audit_id="audit-1",
        official_run_id="run-1",
        parent_cycle_id="cycle-1",
        prediction_id="prediction-1",
        observation_id="observation-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        disposition="POLICY_ABSTENTION",
        first_causal_blocker=blocker,
        prediction_action="NO_TRADE",
        prediction_direction="BEARISH",
        prediction_eligibility="INELIGIBLE",
        evaluation_present=True,
        trade_planner_reached=planner,
        entry_observation_present=entry,
        prediction_blockers=(
            blocker,
            "POLICY_INELIGIBLE",
        ),
        provider_incident_ids=(),
        evaluation_snapshot={
            "candidate": {
                "direction": "BEARISH",
                "eligibility": "INELIGIBLE",
                "reasons": [
                    "DIRECTIONAL_POLICY_EVALUATED",
                ],
            },
            "pre_entry_action": {
                "reasons": [
                    "REGIME_BLOCKED",
                ],
            },
            "option_ranking": {
                "status": "BLOCKED",
            },
        },
        selected_planning_snapshot=(
            {
                "status": "BLOCKED",
            }
            if planner
            else None
        ),
    )


def _policy():
    return CanonicalDirectionalPolicyV1(
        policy_id="policy-1",
        symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        direction="BEARISH",
        decision="NO_TRADE",
        supporting_families=(
            "TECHNICAL",
        ),
        opposing_families=(),
        agreement_strength=70.0,
        evidence_strength=60.0,
        confidence=52.0,
        score=52.0,
        blockers=("REGIME_BLOCKED",),
        warnings=(),
        contradictions=(),
        entry_restrictions=(
            "REGIME_BLOCKED",
        ),
        reasons=(
            "REGIME_BLOCKED",
        ),
        invalidation_reasons=(),
        source_ids=("source-1",),
    )


def test_projection_preserves_authoritative_blocker():
    result = build_task9_decision_observability(
        audit=_audit(),
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert (
        type(result)
        is Task9DecisionObservabilityV1
    )
    assert (
        result.first_causal_blocker
        == "REGIME_BLOCKED"
    )
    assert result.concurrent_blockers == (
        "REGIME_BLOCKED",
        "POLICY_INELIGIBLE",
    )


def test_projection_exposes_threshold_distance():
    result = build_task9_decision_observability(
        audit=_audit(),
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert result.actual_confidence == 52.0
    assert result.required_confidence == 55.0
    assert result.confidence_margin == -3.0

    assert result.supporting_family_count == 1
    assert result.required_family_count == 2
    assert result.family_margin == -1


def test_projection_is_read_only_not_policy_authority():
    audit = _audit()

    result = build_task9_decision_observability(
        audit=audit,
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert result.action == audit.prediction_action
    assert (
        result.direction
        == audit.prediction_direction
    )
    assert (
        result.eligibility
        == audit.prediction_eligibility
    )


def test_stage_reach_comes_from_existing_audit():
    result = build_task9_decision_observability(
        audit=_audit(
            planner=False,
            entry=False,
        ),
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert result.candidate_reached is True
    assert result.ranking_reached is True
    assert result.planning_reached is False
    assert (
        result.capital_authority_reached
        is False
    )
    assert result.paper_entry_reached is False


def test_provider_participation_is_descriptive_only():
    provider = Task9ProviderParticipationV1(
        capability="BFO_OPTION_GREEKS",
        selected=False,
        called=False,
        used=False,
        available=False,
        reason=(
            "OPTION_GREEKS_PROVIDER_"
            "CAPABILITY_UNAVAILABLE"
        ),
    )

    result = build_task9_decision_observability(
        audit=_audit(),
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
        provider_participation=(provider,),
    )

    assert result.provider_participation == (
        provider,
    )

    assert (
        result.provider_participation[0].called
        is False
    )


def test_provider_used_requires_call():
    with pytest.raises(ValueError):
        Task9ProviderParticipationV1(
            capability="NFO_OPTION_GREEKS",
            selected=True,
            called=False,
            used=True,
        )


def test_observability_cannot_enable_live_execution():
    result = build_task9_decision_observability(
        audit=_audit(),
        canonical_policy=_policy(),
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert result.execution_mode == "PAPER"
    assert (
        result.broker_order_submission
        is False
    )
    assert (
        result.live_execution_eligible
        is False
    )


def test_thresholds_must_come_with_policy():
    with pytest.raises(ValueError):
        build_task9_decision_observability(
            audit=_audit(),
            canonical_policy=None,
            required_confidence=55.0,
            required_directional_families=2,
        )
