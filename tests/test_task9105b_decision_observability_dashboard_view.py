from datetime import datetime, timezone

from services.dashboard_read_models.task9_decision_observability_view_v1 import (
    Task9DecisionObservabilityDashboardViewV1,
    build_task9_decision_observability_dashboard_view,
)
from services.contracts.task9_decision_observability_v1 import (
    Task9DecisionObservabilityV1,
    Task9ProviderParticipationV1,
)


def _observability():
    return Task9DecisionObservabilityV1(
        audit_id="audit-1",
        parent_cycle_id="cycle-1",
        prediction_id="prediction-1",
        market="NIFTY",
        exchange="NSE",
        action="NO_TRADE",
        direction="BEARISH",
        eligibility="INELIGIBLE",
        first_causal_blocker="POLICY_INELIGIBLE",
        concurrent_blockers=(
            "POLICY_INELIGIBLE",
        ),
        decision_reasons=(
            "INSUFFICIENT_DIRECTIONAL_FAMILIES",
        ),
        actual_confidence=53.0,
        required_confidence=55.0,
        confidence_margin=-2.0,
        supporting_family_count=1,
        required_family_count=2,
        family_margin=-1,
        supporting_families=(
            "TECHNICAL",
        ),
        opposing_families=(),
        candidate_reached=True,
        ranking_reached=True,
        planning_reached=False,
        capital_authority_reached=False,
        paper_entry_reached=False,
        provider_participation=(
            Task9ProviderParticipationV1(
                capability="SPOT_QUOTES",
                selected=True,
                called=True,
                used=True,
                available=True,
                reason="USED",
            ),
        ),
    )


def test_dashboard_view_projects_core_fields():
    result = (
        build_task9_decision_observability_dashboard_view(
            _observability()
        )
    )

    assert (
        type(result)
        is Task9DecisionObservabilityDashboardViewV1
    )

    assert result.market == "NIFTY"
    assert result.action == "NO_TRADE"
    assert result.direction == "BEARISH"
    assert result.eligibility == "INELIGIBLE"
    assert (
        result.first_blocker
        == "POLICY_INELIGIBLE"
    )


def test_dashboard_view_formats_threshold_distance():
    result = (
        build_task9_decision_observability_dashboard_view(
            _observability()
        )
    )

    assert result.confidence_text == (
        "53.0 / 55.0 (-2.0)"
    )

    assert result.family_text == (
        "1 / 2 (-1)"
    )


def test_dashboard_view_preserves_stage_reach():
    result = (
        build_task9_decision_observability_dashboard_view(
            _observability()
        )
    )

    assert result.candidate_reached is True
    assert result.ranking_reached is True
    assert result.planning_reached is False
    assert result.capital_reached is False
    assert result.paper_entry_reached is False


def test_dashboard_view_preserves_blockers():
    result = (
        build_task9_decision_observability_dashboard_view(
            _observability()
        )
    )

    assert result.blocker_count == 1
    assert result.blockers == (
        "POLICY_INELIGIBLE",
    )


def test_dashboard_view_provider_summary():
    result = (
        build_task9_decision_observability_dashboard_view(
            _observability()
        )
    )

    assert len(result.provider_summary) == 1

    text = result.provider_summary[0]

    assert "SPOT_QUOTES" in text
    assert "selected=True" in text
    assert "called=True" in text
    assert "used=True" in text


def test_dashboard_view_unavailable_thresholds():
    source = Task9DecisionObservabilityV1(
        audit_id="audit-2",
        parent_cycle_id="cycle-2",
        prediction_id="prediction-2",
        market="SENSEX",
        exchange="BSE",
        action="NO_TRADE",
        direction="NEUTRAL",
        eligibility="INELIGIBLE",
        first_causal_blocker="REGIME_BLOCKED",
        concurrent_blockers=(
            "REGIME_BLOCKED",
        ),
        decision_reasons=(),
        actual_confidence=None,
        required_confidence=None,
        confidence_margin=None,
        supporting_family_count=None,
        required_family_count=None,
        family_margin=None,
        supporting_families=(),
        opposing_families=(),
        candidate_reached=True,
        ranking_reached=False,
        planning_reached=False,
        capital_authority_reached=False,
        paper_entry_reached=False,
    )

    result = (
        build_task9_decision_observability_dashboard_view(
            source
        )
    )

    assert result.confidence_text == "Unavailable"
    assert result.family_text == "Unavailable"


def test_dashboard_view_is_projection_only():
    source = _observability()

    result = (
        build_task9_decision_observability_dashboard_view(
            source
        )
    )

    assert result.action == source.action
    assert result.direction == source.direction
    assert result.eligibility == source.eligibility
