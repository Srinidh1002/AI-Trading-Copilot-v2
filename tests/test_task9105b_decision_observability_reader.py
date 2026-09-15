from datetime import datetime, timezone

import pytest

from services.certification.task9_decision_observability_reader import (
    read_task9_decision_observability,
)
from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
)
from services.contracts.canonical_directional_policy_v1 import (
    CanonicalDirectionalPolicyV1,
)
from services.contracts.task9_decision_observability_v1 import (
    Task9ProviderParticipationV1,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
)


NOW = datetime(
    2026,
    8,
    25,
    11,
    0,
    tzinfo=timezone.utc,
)


def _audit():
    return Task9LiveDecisionAuditV1(
        audit_id="audit-reader-1",
        official_run_id="run-reader-1",
        parent_cycle_id="cycle-reader-1",
        prediction_id="prediction-reader-1",
        observation_id="observation-reader-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        disposition="POLICY_ABSTENTION",
        first_causal_blocker=(
            "POLICY_INELIGIBLE"
        ),
        prediction_action="NO_TRADE",
        prediction_direction="BEARISH",
        prediction_eligibility="INELIGIBLE",
        evaluation_present=True,
        trade_planner_reached=False,
        entry_observation_present=False,
        prediction_blockers=(
            "POLICY_INELIGIBLE",
        ),
        provider_incident_ids=(),
        evaluation_snapshot={
            "candidate": {
                "direction": "BEARISH",
                "eligibility": "INELIGIBLE",
                "reasons": [
                    "INSUFFICIENT_DIRECTIONAL_FAMILIES",
                ],
            },
            "option_ranking": {
                "status": "READY",
            },
        },
        selected_planning_snapshot=None,
    )


def _policy(
    audit,
):
    return CanonicalDirectionalPolicyV1(
        policy_id="policy-reader-1",
        symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        direction="BEARISH",
        decision="NO_TRADE",
        supporting_families=(
            "TECHNICAL",
        ),
        opposing_families=(),
        agreement_strength=60.0,
        evidence_strength=60.0,
        confidence=53.0,
        score=53.0,
        blockers=(),
        warnings=(),
        contradictions=(),
        entry_restrictions=(
            "POLICY_INELIGIBLE",
        ),
        reasons=(
            "INSUFFICIENT_DIRECTIONAL_FAMILIES",
        ),
        invalidation_reasons=(),
        source_ids=("technical-1",),
    )


def _providers(
    audit,
):
    return (
        Task9ProviderParticipationV1(
            capability="SPOT_QUOTES",
            selected=True,
            called=True,
            used=True,
            available=True,
            reason="USED",
        ),
    )


def test_reader_recovers_existing_persisted_audit(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    audit = _audit()
    store.save(audit)

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id=audit.prediction_id,
        policy_reader=_policy,
        provider_reader=_providers,
        required_confidence=55.0,
        required_directional_families=2,
    )

    assert result is not None
    assert result.audit_id == audit.audit_id
    assert (
        result.first_causal_blocker
        == "POLICY_INELIGIBLE"
    )
    assert result.confidence_margin == -2.0
    assert result.family_margin == -1


def test_reader_does_not_create_second_store(
    tmp_path,
):
    path = tmp_path / "live-decision-audit.json"

    store = Task9LiveDecisionAuditStore(path)

    audit = _audit()
    store.save(audit)

    files_before = {
        item.name
        for item in tmp_path.iterdir()
    }

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id=audit.prediction_id,
    )

    files_after = {
        item.name
        for item in tmp_path.iterdir()
    }

    assert result is not None
    assert files_after == files_before
    assert files_after == {
        "live-decision-audit.json",
    }


def test_reader_missing_prediction_is_none(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    store.save(_audit())

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id="missing-prediction",
    )

    assert result is None


def test_reader_without_policy_has_no_thresholds(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    audit = _audit()
    store.save(audit)

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id=audit.prediction_id,
    )

    assert result is not None
    assert result.actual_confidence is None
    assert result.required_confidence is None
    assert result.confidence_margin is None

    assert (
        result.supporting_family_count
        is None
    )
    assert result.required_family_count is None
    assert result.family_margin is None


def test_policy_requires_authoritative_thresholds(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    audit = _audit()
    store.save(audit)

    with pytest.raises(ValueError):
        read_task9_decision_observability(
            audit_store=store,
            prediction_id=audit.prediction_id,
            policy_reader=_policy,
        )


def test_reader_provider_projection_is_descriptive(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    audit = _audit()
    store.save(audit)

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id=audit.prediction_id,
        provider_reader=_providers,
    )

    assert result is not None
    assert len(result.provider_participation) == 1
    assert (
        result.provider_participation[0].used
        is True
    )


def test_reader_keeps_paper_only_safety(
    tmp_path,
):
    store = Task9LiveDecisionAuditStore(
        tmp_path / "live-decision-audit.json"
    )

    audit = _audit()
    store.save(audit)

    result = read_task9_decision_observability(
        audit_store=store,
        prediction_id=audit.prediction_id,
    )

    assert result is not None
    assert result.execution_mode == "PAPER"
    assert (
        result.broker_order_submission
        is False
    )
    assert (
        result.live_execution_eligible
        is False
    )
