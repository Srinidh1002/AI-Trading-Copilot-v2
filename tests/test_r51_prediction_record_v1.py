from dataclasses import FrozenInstanceError, replace

import pytest

from services.contracts.prediction_record_v1 import PredictionRecordV1
from test_two_market_decision_contracts_v1 import child


def record(**changes):
    candidate = child("NIFTY").candidate
    values = dict(
        prediction_id="prediction:parent-1:NIFTY:NSE",
        parent_cycle_id="parent-1",
        decision_result_id="decision-1",
        child_result_id="child-NIFTY",
        observation_id=candidate.observation_id,
        underlying_symbol="NIFTY",
        exchange="NSE",
        requested_at=candidate.requested_at,
        completed_at=candidate.received_at,
        market_timestamp=candidate.market_timestamp,
        received_at=candidate.received_at,
        start_underlying_price=25000.0,
        terminal_status="COMPLETED",
        candidate_id=candidate.candidate_id,
        predicted_direction="BULLISH",
        predicted_action="CALL",
        eligibility="ELIGIBLE",
        confidence=75.0,
        score=75.0,
        rank_value=75.0,
        eligible_for_comparison=True,
        outcome_reason="SELECTED",
        parent_decision="SELECTED",
        parent_selected=True,
    )
    values.update(changes)
    return PredictionRecordV1(**values)


def test_record_is_immutable_deterministic_and_paper_only():
    value = record()
    assert value.to_json() == record().to_json()
    assert len(value.semantic_hash) == 64
    with pytest.raises(FrozenInstanceError):
        value.score = 10.0
    with pytest.raises(ValueError):
        replace(value, execution_mode="LIVE")
    with pytest.raises(ValueError):
        replace(value, broker_order_submission=True)


def test_wait_record_requires_nonselected_path():
    value = record(predicted_action="WAIT", parent_selected=False, outcome_reason="LOWER_RANK")
    assert value.predicted_action == "WAIT"
    with pytest.raises(ValueError):
        record(predicted_action="WAIT")


def test_noncompleted_record_is_zeroed_and_waiting():
    value = record(
        terminal_status="FAILED",
        candidate_id=None,
        market_timestamp=None,
        predicted_direction="UNAVAILABLE",
        predicted_action="WAIT",
        eligibility="UNAVAILABLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="CHILD_FAILED",
        parent_decision="NO_TRADE",
        parent_selected=False,
        errors=("CANDIDATE_COMPOSITION_FAILED",),
    )
    assert value.terminal_status == "FAILED"


def test_failure_diagnostic_serializes_as_a_plain_bounded_mapping():
    value = record(
        terminal_status="FAILED",
        candidate_id=None,
        market_timestamp=None,
        predicted_direction="UNAVAILABLE",
        predicted_action="WAIT",
        eligibility="UNAVAILABLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="CHILD_FAILED",
        parent_decision="NO_TRADE",
        parent_selected=False,
        errors=("CANDIDATE_COMPOSITION_FAILED",),
        failure_diagnostic={
            "failure_stage": "ANALYSIS_AUTHORITY",
            "exception_class": "ValueError",
            "stable_failure_code": "CANDIDATE_COMPOSITION_FAILED",
        },
    )

    assert dict(value.failure_diagnostic) == {
        "failure_stage": "ANALYSIS_AUTHORITY",
        "exception_class": "ValueError",
        "stable_failure_code": "CANDIDATE_COMPOSITION_FAILED",
    }
    assert value.to_dict()["failure_diagnostic"] == dict(
        value.failure_diagnostic
    )
    assert "mappingproxy" not in value.to_json().lower()


def test_start_underlying_price_is_required_positive_finite():
    for value in (0.0, -1.0, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            record(start_underlying_price=value)
