from datetime import datetime, timedelta
import math

import pytest

from services.contracts.final_decision_v1 import (
    AuthorizationStatus, DataHealthSummary, DecisionValidationError,
    ExecutionStatus, FinalDecisionV1, RiskSummary, TradePlanV1,
    from_live_option_pipeline_response, from_master_decision_response,
    from_trade_engine_response, to_paper_execution_candidate,
)


NOW = datetime.fromisoformat("2026-07-25T10:00:00+05:30")


def plan(**changes):
    values = {"entry_price": 100, "stop_loss": 95, "targets": (110, 120), "quantity": 1, "risk_reward_ratio": 2, "maximum_planned_loss": 5}
    values.update(changes)
    return TradePlanV1(**values)


def decision(**changes):
    values = {"snapshot_id": "snapshot-1", "symbol": "NIFTY", "exchange": "NSE", "instrument_type": "INDEX", "created_at": NOW, "market_timestamp": NOW - timedelta(seconds=5), "confidence": 80, "data_quality_score": 90}
    values.update(changes)
    return FinalDecisionV1(**values)


def test_valid_wait_hold_and_analysis_only_buy():
    wait = decision()
    hold = decision(action="HOLD")
    analysis = decision(action="BUY", authorization_status="ANALYSIS_ONLY")
    assert wait.validation_passed and hold.validation_passed and analysis.validation_passed
    assert all(item.execution_status == "NOT_REQUESTED" for item in (wait, hold, analysis))


@pytest.mark.parametrize("action,authorization", [("BUY", "BLOCKED"), ("BUY", "PAPER_READY"), ("SELL", "MANUAL_APPROVAL_REQUIRED"), ("SELL", "AUTHORIZED")])
def test_valid_directional_authorization_states(action, authorization):
    result = decision(action=action, authorization_status=authorization, trade_plan=plan())
    assert result.validation_passed and result.authorization_status == authorization


@pytest.mark.parametrize("changes", [
    {"action": "WAIT", "authorization_status": "AUTHORIZED"},
    {"action": "HOLD", "execution_status": "SUBMITTED"},
    {"action": "BUY", "authorization_status": "BLOCKED", "execution_status": "SUBMITTED", "trade_plan": plan()},
    {"action": "BUY", "authorization_status": "PAPER_READY"},
    {"action": "SELL", "authorization_status": "AUTHORIZED"},
    {"data_health": DataHealthSummary(overall_status="INVALID", validation_passed=False, critical_errors=("bad candle",))},
    {"risk": RiskSummary(risk_status="REJECTED")},
])
def test_invalid_authorization_combinations_fail_closed(changes):
    result = decision(**changes)
    assert result.validation_passed is False
    assert result.authorization_status == "BLOCKED"


@pytest.mark.parametrize("field,value", [("confidence", math.nan), ("technical_score", math.inf), ("trade_quality_score", 101), ("risk_score", -1)])
def test_invalid_scores_fail_closed(field, value):
    result = decision(**{field: value})
    assert not result.validation_passed and result.authorization_status == "BLOCKED"


@pytest.mark.parametrize("changes", [{"expiry": "30JUL2026"}, {"strike": math.inf}, {"option_type": "CALL"}, {"trace_metadata": {"live": object()}}])
def test_invalid_optional_identity_or_metadata_fails_closed_and_still_serializes(changes):
    result = decision(**changes)
    assert not result.validation_passed and result.authorization_status == "BLOCKED"
    assert "final_decision.v1" in result.to_json()


@pytest.mark.parametrize("changes", [
    {"quantity": -1}, {"stop_loss": math.nan}, {"targets": ()}, {"entry_price": -1},
])
def test_invalid_trade_plan_values_raise_documented_error(changes):
    with pytest.raises(DecisionValidationError):
        plan(**changes)


def test_serialization_is_deterministic_and_round_trips():
    value = decision(action="BUY", authorization_status="PAPER_READY", trade_plan=plan(), supporting_reasons=("A", "B"), engine_versions={"strategy": "1"})
    rebuilt = FinalDecisionV1.from_dict(value.to_dict())
    assert value.to_json() == rebuilt.to_json()


@pytest.mark.parametrize("status,expected_action,expected_authorization", [
    ("NO_TRADE", "WAIT", "BLOCKED"), ("MARKET_CLOSED", "WAIT", "BLOCKED"),
    ("STALE_MARKET_DATA", "WAIT", "BLOCKED"), ("TRADE_REJECTED", "WAIT", "BLOCKED"),
    ("UNKNOWN_STATE", "WAIT", "BLOCKED"),
])
def test_legacy_blocking_statuses_map_fail_closed(status, expected_action, expected_authorization):
    result = from_live_option_pipeline_response({"decision": status, "snapshot_id": "s", "symbol": "NIFTY", "timestamp": NOW.isoformat()}, reference_time=NOW)
    assert (result.action, result.authorization_status) == (expected_action, expected_authorization)


@pytest.mark.parametrize("status,direction,expected_action,expected_option", [
    ("TRADE_READY", "BULLISH", "BUY", None), ("TRADE_ALLOWED", "BEARISH", "SELL", None),
    ("BUY CE", "", "BUY", "CE"), ("BUY PE", "", "SELL", "PE"),
])
def test_legacy_directional_mapping_is_explicit(status, direction, expected_action, expected_option):
    payload = {"decision": status, "direction": direction, "snapshot_id": "s", "symbol": "NIFTY", "timestamp": NOW.isoformat(), "entry": 100, "stop_loss": 95, "target1": 110, "risk_reward_ratio": 2, "approval_status": "APPROVED", "entry_allowed": True}
    result = from_live_option_pipeline_response(payload, reference_time=NOW)
    assert result.action == expected_action and result.option_type == expected_option
    if status == "TRADE_READY": assert result.authorization_status == "MANUAL_APPROVAL_REQUIRED"
    if status == "TRADE_ALLOWED": assert result.authorization_status == "PAPER_READY"


def test_trade_master_and_live_adapters_preserve_safe_fields_and_warn_unmapped():
    payload = {"decision": "BUY CE", "snapshot_id": "s", "symbol": "NIFTY", "exchange": "NSE", "timestamp": NOW.isoformat(), "confidence": 77, "decision_score": 70, "institutional_score": 60, "reason": "trend confirms", "entry": 100, "stop_loss": 95, "target1": 110, "unknown": object()}
    trade, master, live = (from_trade_engine_response(payload, NOW), from_master_decision_response(payload, NOW), from_live_option_pipeline_response(payload, NOW))
    assert trade.confidence == 77 and master.supporting_reasons == ("trend confirms",)
    assert live.trade_plan is not None and any("Unmapped" in warning for warning in trade.warnings)


def test_missing_snapshot_id_is_blocked_and_timestamp_validation_is_explicit():
    legacy = from_trade_engine_response({"decision": "BUY", "symbol": "NIFTY"}, reference_time=NOW)
    assert legacy.authorization_status == "BLOCKED" and not legacy.validation_passed
    with pytest.raises(DecisionValidationError):
        decision(market_timestamp="not-a-timestamp")


def test_paper_candidate_is_only_available_for_valid_authorized_directional_plan():
    eligible = decision(action="BUY", authorization_status="PAPER_READY", trade_plan=plan())
    assert to_paper_execution_candidate(eligible)["trade_action"] == "EXECUTE"
    for value in (decision(), decision(action="HOLD"), decision(action="BUY", authorization_status="BLOCKED", trade_plan=plan())):
        assert to_paper_execution_candidate(value) is None


def test_construction_and_adapters_do_not_execute_paper_or_provider_code():
    result = from_trade_engine_response({"decision": "NO_TRADE", "snapshot_id": "s", "symbol": "NIFTY", "timestamp": NOW.isoformat()}, NOW)
    assert result.execution_status == ExecutionStatus.NOT_REQUESTED.value
