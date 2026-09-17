from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
    build_task9_live_decision_audit,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
    task9_live_decision_audit_from_dict,
)
from tests.test_regime_candidate_blocker_classification import (
    _evaluate,
)


IST = ZoneInfo("Asia/Kolkata")

NOW = datetime(
    2026,
    8,
    20,
    10,
    0,
    tzinfo=IST,
)


def _audit(
    *,
    market="NIFTY",
    exchange="NSE",
    prediction_id="pred-1",
    evaluation=None,
    blockers=None,
):
    if (
        evaluation is None
        and blockers is None
    ):
        evaluation = _evaluate()

    candidate = (
        None
        if evaluation is None
        else evaluation.candidate
    )

    return build_task9_live_decision_audit(
        audit_id=(
            f"audit:{prediction_id}"
        ),
        official_run_id=(
            "task9-live-test"
        ),
        parent_cycle_id=(
            "parent-1"
        ),
        prediction_id=prediction_id,
        observation_id=(
            f"obs:{prediction_id}"
        ),
        underlying_symbol=market,
        exchange=exchange,
        evaluated_at=NOW,
        evaluation=evaluation,
        prediction_action=(
            "NO_TRADE"
            if evaluation is not None
            else None
        ),
        prediction_direction=(
            None
            if candidate is None
            else getattr(
                candidate,
                "direction",
                None,
            )
        ),
        prediction_eligibility=(
            None
            if candidate is None
            else getattr(
                candidate,
                "eligibility",
                None,
            )
        ),
        prediction_blockers=(
            (
                ("REGIME_BLOCKED",)
                if (
                    candidate is not None
                    and "REGIME_BLOCKED"
                    in candidate.blockers
                )
                else ()
            )
            if blockers is None
            else blockers
        ),
        selected_planning=None,
        paper_observation=None,
        provider_incident_ids=(),
    )


def test_valid_regime_block_is_policy_abstention_not_missing_evidence():
    result = _evaluate()

    candidate_before = (
        result.candidate
    )
    evidence_before = (
        result.evidence
    )
    pre_entry_before = (
        result.pre_entry_action
    )

    audit = _audit(
        evaluation=result
    )

    assert (
        audit.disposition
        == "POLICY_ABSTENTION"
    )

    assert (
        audit.first_causal_blocker
        == "REGIME_BLOCKED"
    )

    assert (
        "EVIDENCE_UNAVAILABLE_REGIME"
        not in audit.prediction_blockers
    )

    snapshot = (
        audit.evaluation_snapshot
    )

    assert (
        snapshot["candidate"][
            "eligibility"
        ]
        == "UNAVAILABLE"
    )

    assert (
        snapshot["evidence"][
            "regime"
        ][
            "entry_suitability"
        ]
        == "NOT_SUITABLE"
    )

    assert (
        snapshot[
            "pre_entry_action"
        ][
            "action"
        ]
        == "NO_TRADE"
    )

    # Projection is observational only.
    assert (
        result.candidate
        is candidate_before
    )
    assert (
        result.evidence
        is evidence_before
    )
    assert (
        result.pre_entry_action
        is pre_entry_before
    )


def test_missing_regime_is_distinct_evidence_unavailable():
    audit = _audit(
        evaluation=None,
        blockers=(
            "EVIDENCE_UNAVAILABLE_REGIME",
            "NO_ELIGIBLE_MARKET",
        ),
    )

    assert (
        audit.disposition
        == "EVIDENCE_UNAVAILABLE"
    )

    assert (
        audit.first_causal_blocker
        == "EVIDENCE_UNAVAILABLE_REGIME"
    )

    assert (
        audit.evaluation_present
        is False
    )

    assert dict(
        audit.evaluation_snapshot
    ) == {}


def test_no_eligible_market_remains_derived_when_regime_is_causal():
    result = _evaluate()

    audit = build_task9_live_decision_audit(
        audit_id="audit-derived",
        official_run_id="run",
        parent_cycle_id="parent",
        prediction_id="pred-derived",
        observation_id="obs-derived",
        underlying_symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        evaluation=result,
        prediction_action="NO_TRADE",
        prediction_direction="UNAVAILABLE",
        prediction_eligibility="UNAVAILABLE",
        prediction_blockers=(
            "NO_ELIGIBLE_MARKET",
            "REGIME_BLOCKED",
        ),
    )

    assert (
        audit.first_causal_blocker
        == "REGIME_BLOCKED"
    )


def test_contract_round_trip_is_exact():
    audit = _audit()

    recovered = (
        task9_live_decision_audit_from_dict(
            audit.to_dict()
        )
    )

    assert recovered == audit


def test_ranking_projection_preserves_selected_contract_identity():
    """Task 9 audit projection must retain the derived ranking selection."""
    result = _evaluate()
    ranking = result.evidence.contract_ranking

    assert ranking.ranking_status == "RANKED_WITH_WARNINGS"
    assert ranking.ranked_candidates
    selected_id = (
        ranking.ranked_candidates[0].contract.contract_id
    )

    audit = _audit(evaluation=result)
    projected = audit.evaluation_snapshot["evidence"][
        "contract_ranking"
    ]

    assert projected["ranking_status"] == "RANKED_WITH_WARNINGS"
    assert projected["selected_contract_id"] == selected_id
    assert projected["eligible_candidate_count"] == len(
        ranking.ranked_candidates
    )
    assert "selected_candidate" not in projected


def test_ranking_contract_serialization_preserves_selected_identity():
    result = _evaluate()
    ranking = result.evidence.contract_ranking

    # The typed contract is the source of truth for both successful statuses;
    # the direct RANKED invariant is covered by the ranking-contract suite.
    payload = ranking.to_dict()
    assert payload["selected_contract_id"] == (
        ranking.ranked_candidates[0].contract.contract_id
    )
    assert payload["eligible_candidate_count"] == len(
        ranking.ranked_candidates
    )


def test_store_is_restart_safe_and_idempotent(
    tmp_path,
):
    path = (
        tmp_path
        / "live-decision-audit.json"
    )

    first = (
        Task9LiveDecisionAuditStore(
            path
        )
    )

    audit = _audit()

    assert (
        first.save(audit)
        == "SAVED"
    )

    second = (
        Task9LiveDecisionAuditStore(
            path
        )
    )

    assert (
        second.recover(
            audit.prediction_id
        )
        == audit
    )

    assert (
        second.save(audit)
        == "DUPLICATE_SAME_PAYLOAD"
    )


def test_conflicting_duplicate_fails_closed(
    tmp_path,
):
    store = (
        Task9LiveDecisionAuditStore(
            tmp_path
            / "live-decision-audit.json"
        )
    )

    audit = _audit()

    assert (
        store.save(audit)
        == "SAVED"
    )

    conflicting = replace(
        audit,
        disposition=(
            "OTHER_INELIGIBLE"
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "conflicting Task 9 live decision audit"
        ),
    ):
        store.save(
            conflicting
        )


def test_corrupt_store_fails_closed(
    tmp_path,
):
    path = (
        tmp_path
        / "live-decision-audit.json"
    )

    path.write_text(
        '{"version":1,"records":',
        encoding="utf-8",
    )

    store = (
        Task9LiveDecisionAuditStore(
            path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "invalid Task 9 live decision audit store"
        ),
    ):
        store.list_all()


def test_nifty_and_sensex_are_independent(
    tmp_path,
):
    store = (
        Task9LiveDecisionAuditStore(
            tmp_path
            / "live-decision-audit.json"
        )
    )

    nifty = _audit(
        market="NIFTY",
        exchange="NSE",
        prediction_id="nifty-1",
        evaluation=None,
        blockers=(
            "EVIDENCE_UNAVAILABLE_REGIME",
        ),
    )

    sensex = _audit(
        market="SENSEX",
        exchange="BSE",
        prediction_id="sensex-1",
        evaluation=None,
        blockers=(
            "EVIDENCE_UNAVAILABLE_OPTION_CHAIN",
        ),
    )

    store.save(nifty)
    store.save(sensex)

    assert (
        store.recover(
            "nifty-1"
        )
        == nifty
    )

    assert (
        store.recover(
            "sensex-1"
        )
        == sensex
    )

    assert len(
        store.list_all()
    ) == 2


def test_contract_rejects_live_execution():
    audit = _audit()

    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        replace(
            audit,
            live_execution_eligible=True,
        )
