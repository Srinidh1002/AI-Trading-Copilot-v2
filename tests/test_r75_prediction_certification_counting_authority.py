from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from services.certification.prediction_certification_counting_evaluator import (
    evaluate_prediction_certification_counting,
)
from services.contracts.paper_certification_counting_policy_v1 import (
    PaperCertificationCountingPolicyV1,
)
from services.contracts.prediction_certification_counting_input_v1 import (
    PredictionCertificationCountingInputV1,
)
from services.contracts.prediction_outcome_evaluation_input_v1 import (
    PredictionOutcomeEvaluationInputV1,
)
from services.paper_orchestration.prediction_outcome_evaluator import (
    evaluate_prediction_outcome,
)
from test_r51_prediction_record_v1 import record


SYSTEM_VERSION = "system-2026.08.05"
POLICY_VERSION = "counting-policy-1"
PROVIDER_VERSION = "angel-readonly-1"
RUN_ID = "official-run-1"


def policy(**changes):
    values = dict(
        policy_id="paper-counting-policy",
        policy_version=POLICY_VERSION,
        accepted_system_version=SYSTEM_VERSION,
        accepted_provider_version=PROVIDER_VERSION,
    )
    values.update(changes)
    return PaperCertificationCountingPolicyV1(
        **values
    )


def outcome(prediction=None):
    prediction = prediction or record()
    due = prediction.completed_at + timedelta(
        minutes=15
    )
    return evaluate_prediction_outcome(
        PredictionOutcomeEvaluationInputV1(
            prediction=prediction,
            evaluation_observation_id=(
                "counting-evaluation-observation"
            ),
            start_underlying_price=(
                prediction.start_underlying_price
            ),
            end_underlying_price=(
                prediction.start_underlying_price
                + 100.0
            ),
            evaluation_due_at=due,
            evaluated_at=due,
            evaluation_horizon_seconds=900.0,
            threshold_percent=0.20,
        )
    )


def counting_input(**changes):
    prediction = changes.pop(
        "prediction",
        record(),
    )
    if "outcome" in changes:
        resolved_outcome = changes.pop("outcome")
    else:
        resolved_outcome = outcome(prediction)

    values = dict(
        prediction=prediction,
        outcome=resolved_outcome,
        record_source="LIVE_REAL_TIME",
        session_status="REAL_TIME_MARKET_SESSION",
        evidence_status="VALID",
        record_run_id=RUN_ID,
        official_run_id=RUN_ID,
        official_start_at=(
            prediction.completed_at
            - timedelta(seconds=1)
        ),
        observed_system_version=SYSTEM_VERSION,
        observed_policy_version=POLICY_VERSION,
        observed_provider_version=PROVIDER_VERSION,
        evaluated_at=(
            resolved_outcome.evaluated_at
            if resolved_outcome is not None
            else prediction.completed_at
        ),
    )
    values.update(changes)
    return PredictionCertificationCountingInputV1(
        **values
    )


def test_policy_is_immutable_deterministic_and_forbids_resets():
    value = policy()

    assert value.to_json() == policy().to_json()
    assert len(value.semantic_hash) == 64

    with pytest.raises(FrozenInstanceError):
        value.policy_version = "changed"

    with pytest.raises(
        ValueError,
        match="cannot be reset",
    ):
        policy(counter_reset_allowed=True)

    with pytest.raises(ValueError):
        policy(include_wait=False)

    with pytest.raises(ValueError):
        policy(include_no_trade=False)


def test_valid_live_completed_prediction_is_included():
    first = evaluate_prediction_certification_counting(
        value=counting_input(),
        policy=policy(),
    )
    second = evaluate_prediction_certification_counting(
        value=counting_input(),
        policy=policy(),
    )

    assert first == second
    assert first.status == "INCLUDED"
    assert first.countable is True
    assert first.pending is False
    assert first.reason_codes == ()
    assert len(first.counting_key) == 64
    assert first.counter_reset_allowed is False


def test_missing_outcome_is_pending_not_counted():
    prediction = record()
    decision = evaluate_prediction_certification_counting(
        value=counting_input(
            prediction=prediction,
            outcome=None,
            evaluated_at=prediction.completed_at,
        ),
        policy=policy(),
    )

    assert decision.status == "PENDING_OUTCOME"
    assert decision.countable is False
    assert decision.pending is True
    assert decision.reason_codes == (
        "OUTCOME_NOT_COMPLETED",
    )


@pytest.mark.parametrize(
    ("record_source", "expected"),
    (
        ("REPLAY", "EXCLUDED_REPLAY"),
        ("BACKTEST", "EXCLUDED_BACKTEST"),
        ("DIAGNOSTIC", "EXCLUDED_DIAGNOSTIC"),
        ("FIXTURE", "EXCLUDED_FIXTURE"),
        ("DEVELOPMENT", "EXCLUDED_DEVELOPMENT"),
    ),
)
def test_non_live_sources_never_count(
    record_source,
    expected,
):
    decision = evaluate_prediction_certification_counting(
        value=counting_input(
            record_source=record_source,
        ),
        policy=policy(),
    )

    assert decision.status == expected
    assert decision.countable is False
    assert decision.pending is False


def test_run_start_session_evidence_and_versions_fail_closed():
    base = counting_input()

    run_mismatch = evaluate_prediction_certification_counting(
        value=replace(
            base,
            record_run_id="different-run",
        ),
        policy=policy(),
    )
    assert run_mismatch.status == (
        "EXCLUDED_RUN_MISMATCH"
    )

    pre_start = evaluate_prediction_certification_counting(
        value=replace(
            base,
            official_start_at=(
                base.prediction.completed_at
                + timedelta(seconds=1)
            ),
        ),
        policy=policy(),
    )
    assert pre_start.status == "EXCLUDED_PRE_START"

    out_of_session = (
        evaluate_prediction_certification_counting(
            value=replace(
                base,
                session_status="OUT_OF_SESSION",
            ),
            policy=policy(),
        )
    )
    assert out_of_session.status == (
        "EXCLUDED_OUT_OF_SESSION"
    )

    invalid_evidence = (
        evaluate_prediction_certification_counting(
            value=replace(
                base,
                evidence_status="INVALID",
            ),
            policy=policy(),
        )
    )
    assert invalid_evidence.status == (
        "EXCLUDED_INVALID_EVIDENCE"
    )

    version_mismatch = (
        evaluate_prediction_certification_counting(
            value=replace(
                base,
                observed_system_version="old-system",
            ),
            policy=policy(),
        )
    )
    assert version_mismatch.status == (
        "EXCLUDED_VERSION_MISMATCH"
    )
    assert version_mismatch.reason_codes == (
        "SYSTEM_VERSION_MISMATCH",
    )


def test_data_incident_is_explicitly_excluded():
    decision = evaluate_prediction_certification_counting(
        value=counting_input(
            evidence_status="DATA_INCIDENT",
            data_incident_codes=(
                "PROVIDER_THROTTLED",
            ),
        ),
        policy=policy(),
    )

    assert decision.status == (
        "EXCLUDED_DATA_INCIDENT"
    )
    assert decision.reason_codes == (
        "PROVIDER_THROTTLED",
    )


def test_wait_and_no_trade_are_countable_after_outcome():
    prediction = record(
        predicted_direction="NEUTRAL",
        predicted_action="WAIT",
        eligibility="INELIGIBLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="INELIGIBLE",
        parent_decision="NO_TRADE",
        parent_selected=False,
    )
    resolved = outcome(prediction)

    decision = evaluate_prediction_certification_counting(
        value=counting_input(
            prediction=prediction,
            outcome=resolved,
            evaluated_at=resolved.evaluated_at,
        ),
        policy=policy(),
    )

    assert decision.status == "INCLUDED"
    assert decision.predicted_action == "WAIT"
    assert decision.parent_decision == "NO_TRADE"
    assert decision.countable is True


def test_market_records_receive_independent_counting_keys():
    nifty_input = counting_input()
    sensex_prediction = replace(
        nifty_input.prediction,
        prediction_id=(
            "prediction:parent-1:SENSEX:BSE"
        ),
        child_result_id="child-SENSEX",
        underlying_symbol="SENSEX",
        exchange="BSE",
    )
    sensex_outcome = outcome(sensex_prediction)
    sensex_input = counting_input(
        prediction=sensex_prediction,
        outcome=sensex_outcome,
        evaluated_at=sensex_outcome.evaluated_at,
    )

    nifty_decision = (
        evaluate_prediction_certification_counting(
            value=nifty_input,
            policy=policy(),
        )
    )
    sensex_decision = (
        evaluate_prediction_certification_counting(
            value=sensex_input,
            policy=policy(),
        )
    )

    assert (
        nifty_decision.counting_key
        != sensex_decision.counting_key
    )
