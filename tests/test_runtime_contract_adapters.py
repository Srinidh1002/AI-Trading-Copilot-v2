from copy import deepcopy
from datetime import datetime

import math
import pandas as pd
import pytest

from services.contracts.final_decision_v1 import to_paper_execution_candidate
from services.contracts.runtime_adapters import (
    build_dashboard_shadow_contracts, build_live_option_shadow_contracts,
    compare_shadow_contracts, serialize_shadow_contracts,
)


NOW = datetime.fromisoformat("2026-07-25T10:00:00+05:30")


def history():
    return pd.DataFrame([["2026-07-25T09:55:00+05:30", 100, 105, 99, 104, 10]], columns=["timestamp", "open", "high", "low", "close", "volume"])


def snapshot(**changes):
    value = {"symbol": "NIFTY", "history": history(), "ltp": 104, "open": 100, "high": 105, "low": 99, "close": 104, "volume": 10, "timestamp": NOW.isoformat(), "market_status": "OPEN", "option_analysis": {}}
    value.update(changes)
    return value


def response(decision="BUY CE", **changes):
    value = {"decision": decision, "confidence": 80, "decision_score": 75, "institutional_score": 70, "reason": "confirmed", "entry": 104, "stop_loss": 99, "target1": 110, "target2": 115, "risk_reward_ratio": 2}
    value.update(changes)
    return value


def test_dashboard_shadow_maps_valid_snapshot_and_decision_without_mutating_legacy_values():
    legacy_snapshot, legacy_response = snapshot(), response()
    before_snapshot, before_response = legacy_snapshot.copy(), deepcopy(legacy_response)
    shadow = build_dashboard_shadow_contracts(legacy_snapshot, legacy_response, reference_time=NOW)
    assert shadow["valid"] and shadow["snapshot_v1"].validation_passed and shadow["decision_v1"].validation_passed
    assert legacy_snapshot == before_snapshot and legacy_response == before_response


@pytest.mark.parametrize("legacy_action,v1_action", [("WAIT", "WAIT"), ("BUY CE", "BUY"), ("BUY PE", "SELL"), ("HOLD", "HOLD")])
def test_dashboard_action_mapping(legacy_action, v1_action):
    shadow = build_dashboard_shadow_contracts(snapshot(), response(legacy_action), reference_time=NOW)
    assert shadow["decision_v1"].action == v1_action


def test_dashboard_missing_optional_sources_are_explicitly_unavailable():
    shadow = build_dashboard_shadow_contracts(snapshot(option_analysis=None), response("WAIT"), reference_time=NOW)
    assert shadow["snapshot_v1"].option_chain_status == "UNAVAILABLE"
    assert "option_chain" in shadow["snapshot_v1"].missing_sources


@pytest.mark.parametrize("bad_snapshot", [snapshot(symbol=""), snapshot(ltp=math.nan)])
def test_invalid_dashboard_input_is_diagnostic_only_and_preserves_legacy_response(bad_snapshot):
    legacy_response = response("WAIT")
    before = deepcopy(legacy_response)
    shadow = build_dashboard_shadow_contracts(bad_snapshot, legacy_response, reference_time=NOW)
    assert not shadow["valid"] and legacy_response == before
    assert shadow["snapshot_v1"] is not None


def test_dashboard_mapping_exception_is_contained():
    bad = snapshot(timestamp="not-a-timestamp")
    shadow = build_dashboard_shadow_contracts(bad, response(), reference_time=NOW)
    assert shadow["snapshot_v1"] is None and shadow["errors"]


@pytest.mark.parametrize("status", ["MARKET_CLOSED", "MARKET_HOLIDAY", "STALE_MARKET_DATA", "NO_TRADE", "TRADE_REJECTED", "UNKNOWN_STATUS"])
def test_live_blocking_statuses_fail_closed(status):
    shadow = build_live_option_shadow_contracts(response(status), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    assert shadow["decision_v1"].action == "WAIT"
    assert shadow["decision_v1"].authorization_status == "BLOCKED"


@pytest.mark.parametrize("status,direction,authorization", [("TRADE_READY", "BULLISH", "MANUAL_APPROVAL_REQUIRED"), ("TRADE_ALLOWED", "BEARISH", "PAPER_READY")])
def test_live_directional_lifecycle_mapping(status, direction, authorization):
    data = response(status, direction=direction, approval_status="APPROVED", entry_allowed=True)
    shadow = build_live_option_shadow_contracts(data, symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    assert shadow["decision_v1"].authorization_status == authorization


def test_live_ambiguous_direction_blocks_and_invalid_plan_is_not_authorized():
    ambiguous = build_live_option_shadow_contracts(response("TRADE_READY", direction="NEUTRAL"), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    invalid_plan = build_live_option_shadow_contracts(response("BUY", stop_loss=None), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    assert ambiguous["decision_v1"].authorization_status == "BLOCKED"
    assert invalid_plan["decision_v1"].authorization_status == "BLOCKED" and not invalid_plan["decision_v1"].validation_passed


def test_live_snapshot_preserves_valid_plan_reason_scores_and_missing_scores():
    shadow = build_live_option_shadow_contracts(response("TRADE_ALLOWED", direction="BULLISH", approval_status="APPROVED", entry_allowed=True, technical_score=None), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    decision = shadow["decision_v1"]
    assert decision.trade_plan is not None and decision.supporting_reasons == ("confirmed",)
    assert decision.confidence == 80 and decision.technical_score is None


def test_comparison_and_serialization_are_deterministic_for_one_shadow_result():
    shadow = build_dashboard_shadow_contracts(snapshot(), response(), reference_time=NOW)
    first, second = compare_shadow_contracts(response(), shadow), compare_shadow_contracts(response(), shadow)
    assert first == second and serialize_shadow_contracts(shadow) == serialize_shadow_contracts(shadow)
    assert first["trade_plan_mapping"] == "VALID"


def test_shadow_and_paper_candidate_remain_non_executing():
    shadow = build_live_option_shadow_contracts(response("TRADE_ALLOWED", direction="BULLISH", approval_status="APPROVED", entry_allowed=True), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    ready = shadow["decision_v1"]
    manual = build_live_option_shadow_contracts(response("TRADE_READY", direction="BULLISH"), symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)["decision_v1"]
    assert to_paper_execution_candidate(ready)["trade_action"] == "EXECUTE"
    assert to_paper_execution_candidate(manual) is None
    for action in ("WAIT", "HOLD"):
        decision = build_dashboard_shadow_contracts(snapshot(), response(action), reference_time=NOW)["decision_v1"]
        assert to_paper_execution_candidate(decision) is None


def test_repeated_shadow_conversions_do_not_mutate_or_call_runtime_services():
    legacy_snapshot, legacy_response = snapshot(), response("WAIT")
    first = build_dashboard_shadow_contracts(legacy_snapshot, legacy_response, reference_time=NOW)
    second = build_dashboard_shadow_contracts(legacy_snapshot, legacy_response, reference_time=NOW)
    assert first["decision_v1"].execution_status == second["decision_v1"].execution_status == "NOT_REQUESTED"
    assert legacy_response["decision"] == "WAIT"


@pytest.mark.parametrize("path,status,direction,approval,expected_action,expected_authorization", [
    ("dashboard", "WAIT", None, None, "WAIT", "BLOCKED"),
    ("dashboard", "HOLD", None, None, "HOLD", "BLOCKED"),
    ("dashboard", "BUY", None, None, "BUY", "ANALYSIS_ONLY"),
    ("dashboard", "SELL", None, None, "SELL", "ANALYSIS_ONLY"),
    ("dashboard", "BUY CE", None, None, "BUY", "ANALYSIS_ONLY"),
    ("dashboard", "BUY PE", None, None, "SELL", "ANALYSIS_ONLY"),
    ("live", "MARKET_CLOSED", None, None, "WAIT", "BLOCKED"),
    ("live", "MARKET_HOLIDAY", None, None, "WAIT", "BLOCKED"),
    ("live", "STALE_MARKET_DATA", None, None, "WAIT", "BLOCKED"),
    ("live", "NO_TRADE", None, None, "WAIT", "BLOCKED"),
    ("live", "TRADE_REJECTED", None, None, "WAIT", "BLOCKED"),
    ("live", "ERROR", None, None, "WAIT", "BLOCKED"),
    ("live", "UNKNOWN", None, None, "WAIT", "BLOCKED"),
    ("live", "TRADE_READY", "BULLISH", None, "BUY", "MANUAL_APPROVAL_REQUIRED"),
    ("live", "TRADE_READY", "BEARISH", None, "SELL", "MANUAL_APPROVAL_REQUIRED"),
    ("live", "TRADE_ALLOWED", "BULLISH", "APPROVED", "BUY", "PAPER_READY"),
    ("live", "TRADE_ALLOWED", "BEARISH", "APPROVED", "SELL", "PAPER_READY"),
    ("live", "TRADE_READY", "NEUTRAL", None, "WAIT", "BLOCKED"),
])
def test_shadow_status_matrix_preserves_legacy_and_never_submits(path, status, direction, approval, expected_action, expected_authorization):
    legacy = response(status)
    if direction is not None: legacy["direction"] = direction
    if approval is not None:
        legacy["approval_status"], legacy["entry_allowed"] = approval, True
    if path == "dashboard":
        shadow = build_dashboard_shadow_contracts(snapshot(), legacy, reference_time=NOW)
    else:
        shadow = build_live_option_shadow_contracts(legacy, symbol="NIFTY", exchange="NSE", market_timestamp=NOW, ltp=100, reference_time=NOW)
    decision = shadow["decision_v1"]
    assert (decision.action, decision.authorization_status, decision.execution_status) == (expected_action, expected_authorization, "NOT_REQUESTED")
    assert legacy["decision"] == status
