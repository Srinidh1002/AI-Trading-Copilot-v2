from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from services.contracts.position_size_result_v1 import PositionSizeResultV1


NOW = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)


def make(**changes):
    values = dict(sizing_result_id="size-1", created_at=NOW, snapshot_id="snapshot-1", analysis_id="analysis-1", decision_id="decision-1", selection_id="selection-1", trade_plan_id="plan-1", contract_id="contract-1", underlying_symbol="NIFTY", exchange="NSE", action="BUY", option_type="CALL", trading_symbol="NIFTY26JUL25000CE", expiry_date=date(2026, 7, 30), strike=25000.0, lot_size=50, entry_price=100.0, stop_loss_price=90.0, target_price=120.0, available_capital=100000.0, capital_limit=10000.0, risk_limit=2000.0, per_unit_risk=10.0, per_lot_risk=500.0, requested_lots=2, approved_lots=1, quantity=50, capital_required=5000.0, maximum_loss=500.0, reward_amount=1000.0, reward_risk_ratio=2.0, sizing_status="APPROVED", risk_approved=True, paper_preparation_eligible=True, execution_eligible=False)
    values.update(changes)
    return PositionSizeResultV1(**values)


def blocked(status="BLOCKED", **changes):
    values = dict(sizing_status=status, risk_approved=False, paper_preparation_eligible=False, execution_eligible=False, blockers=("risk pending",), entry_price=None, stop_loss_price=None, target_price=None, available_capital=None, capital_limit=None, risk_limit=None, per_unit_risk=None, per_lot_risk=None, requested_lots=None, approved_lots=None, quantity=None, capital_required=None, maximum_loss=None, reward_amount=None, reward_risk_ratio=None)
    values.update(changes)
    return make(**values)


@pytest.mark.parametrize("symbol,exchange,action,option_type", [("NIFTY", "NSE", "BUY", "CALL"), ("NIFTY", "NSE", "SELL", "PUT"), ("BANKNIFTY", "NSE", "BUY", "CALL"), ("BANKNIFTY", "NSE", "SELL", "PUT"), ("FINNIFTY", "NSE", "BUY", "CALL"), ("FINNIFTY", "NSE", "SELL", "PUT"), ("SENSEX", "BSE", "BUY", "CALL"), ("SENSEX", "BSE", "SELL", "PUT")])
def test_supported_approved_identities(symbol, exchange, action, option_type):
    assert make(underlying_symbol=symbol, exchange=exchange, action=action, option_type=option_type).sizing_status == "APPROVED"


def test_result_is_frozen_slotted_and_correctly_versioned():
    value = make(); assert value.schema_version == "position_size_result.v1" and not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError): value.quantity = 1


@pytest.mark.parametrize("field,value", [("schema_version", "bad"), ("created_at", datetime(2026, 7, 27, 10)), ("sizing_result_id", ""), ("snapshot_id", ""), ("decision_id", ""), ("selection_id", ""), ("trade_plan_id", ""), ("contract_id", ""), ("underlying_symbol", "BANKNIFTY"), ("exchange", "BSE"), ("action", "WAIT"), ("option_type", "CE"), ("option_type", "PUT"), ("strike", 0), ("strike", -1), ("strike", float("nan")), ("lot_size", 0), ("lot_size", True), ("entry_price", 0), ("stop_loss_price", -1), ("target_price", float("inf")), ("available_capital", 0), ("capital_limit", -1), ("risk_limit", float("nan")), ("per_unit_risk", 0), ("per_lot_risk", -1), ("requested_lots", True), ("approved_lots", -1), ("capital_required", float("inf")), ("maximum_loss", 0), ("reward_amount", -1), ("reward_risk_ratio", float("nan")), ("approved_lots", 3), ("quantity", 100), ("execution_eligible", True)])
def test_invalid_approved_values_are_rejected(field, value):
    changes={field:value}
    if field=="underlying_symbol" and value=="BANKNIFTY": changes["exchange"]="BSE"
    with pytest.raises(ValueError): make(**changes)


@pytest.mark.parametrize("field,value", [("risk_approved", False), ("paper_preparation_eligible", False), ("blockers", ("blocked",)), ("entry_price", None), ("requested_lots", None), ("quantity", None)])
def test_approved_requires_complete_safe_sizing(field, value):
    with pytest.raises(ValueError): make(**{field: value})


@pytest.mark.parametrize("status", ["INSUFFICIENT_CAPITAL", "INVALID_RISK", "LIMIT_EXCEEDED", "BLOCKED", "FAILED"])
def test_non_approved_statuses_require_blockers_and_no_eligibility(status):
    assert blocked(status).sizing_status == status
    with pytest.raises(ValueError): blocked(status, blockers=())
    with pytest.raises(ValueError): blocked(status, risk_approved=True)
    with pytest.raises(ValueError): blocked(status, paper_preparation_eligible=True)


def test_non_approved_results_permit_honest_no_sizing_data():
    value = blocked()
    assert value.quantity is None and value.approved_lots is None and value.capital_required is None and value.maximum_loss is None


@pytest.mark.parametrize("status", ["INSUFFICIENT_CAPITAL", "INVALID_RISK", "LIMIT_EXCEEDED", "BLOCKED", "FAILED"])
def test_non_approved_statuses_also_reject_execution_eligibility(status):
    with pytest.raises(ValueError): blocked(status, execution_eligible=True)


def test_blockers_and_warnings_are_normalized_and_metadata_is_copied():
    metadata = {"source": "synthetic"}; value = blocked(blockers=["blocked"], warnings=["warn"], metadata=metadata); metadata["source"] = "changed"
    assert value.blockers == ("blocked",) and value.warnings == ("warn",) and value.metadata == {"source": "synthetic"}


@pytest.mark.parametrize("metadata", [{"x": float("nan")}, {"x": float("inf")}, {"x": object()}])
def test_unsafe_metadata_is_rejected(metadata):
    with pytest.raises(ValueError): make(metadata=metadata)


def test_serialization_and_semantics_are_deterministic():
    value = make(metadata={"b": 2, "a": 1})
    assert value.to_dict() == value.to_dict() and json.loads(value.to_json())["created_at"].endswith("+00:00")
    assert "sizing_result_id" not in value.semantic_dict() and "created_at" not in value.semantic_dict()


def test_equivalent_semantic_objects_are_deterministic():
    assert make().semantic_dict() == make(sizing_result_id="different", created_at=NOW).semantic_dict()


@pytest.mark.parametrize("field", ["selection_id", "trade_plan_id", "contract_id", "trading_symbol"])
def test_blocked_permits_each_missing_selected_identity(field):
    assert getattr(blocked(**{field: None}), field) is None


def test_blocked_permits_all_selected_contract_identity_absent():
    value = blocked(selection_id=None, trade_plan_id=None, contract_id=None, trading_symbol=None, expiry_date=None, strike=None, lot_size=None, option_type=None)
    assert value.to_dict()["contract_id"] is None and value.to_dict()["strike"] is None


@pytest.mark.parametrize("status", ["INSUFFICIENT_CAPITAL", "INVALID_RISK", "LIMIT_EXCEEDED", "FAILED"])
def test_non_approved_statuses_permit_incomplete_identity(status):
    assert blocked(status, selection_id=None, trade_plan_id=None, contract_id=None, trading_symbol=None, expiry_date=None, strike=None, lot_size=None, option_type=None).sizing_status == status


def test_nullable_identity_serializes_as_null_and_semantics_remain_deterministic():
    value = blocked(selection_id=None, trade_plan_id=None, contract_id=None, trading_symbol=None, expiry_date=None, strike=None, lot_size=None, option_type=None)
    payload = json.loads(value.to_json())
    assert payload["selection_id"] is None and payload["expiry_date"] is None and value.semantic_dict() == value.semantic_dict()


@pytest.mark.parametrize("field", ["selection_id", "trade_plan_id", "contract_id", "trading_symbol", "expiry_date", "strike", "lot_size"])
def test_approved_still_rejects_missing_contract_identity(field):
    with pytest.raises(ValueError): make(**{field: None})


def test_non_approved_result_does_not_fabricate_identifiers():
    value = blocked(selection_id=None, trade_plan_id=None, contract_id=None, trading_symbol=None)
    assert (value.selection_id, value.trade_plan_id, value.contract_id, value.trading_symbol) == (None, None, None, None)


def test_blocked_permits_honest_wait_without_option_type():
    value = blocked(action="WAIT", option_type=None)
    assert (value.action, value.option_type) == ("WAIT", None)


@pytest.mark.parametrize("status", ["INSUFFICIENT_CAPITAL", "INVALID_RISK", "LIMIT_EXCEEDED", "FAILED"])
def test_each_non_approved_status_permits_wait_without_option_type(status):
    assert blocked(status, action="WAIT", option_type=None).sizing_status == status


def test_wait_serialization_and_semantics_are_deterministic_without_fabrication():
    value = blocked(action="WAIT", option_type=None)
    payload = json.loads(value.to_json())
    assert payload["action"] == "WAIT" and payload["option_type"] is None and value.semantic_dict()["action"] == "WAIT"


@pytest.mark.parametrize("field,value", [("action", "WAIT"), ("option_type", None), ("option_type", "PUT")])
def test_approved_remains_strictly_directional(field, value):
    with pytest.raises(ValueError): make(**{field: value})


def test_approved_sell_put_remains_valid():
    assert make(action="SELL", option_type="PUT").sizing_status == "APPROVED"


@pytest.mark.parametrize("action,option_type", [("BUY", "PUT"), ("SELL", "CALL")])
def test_approved_rejects_crossed_direction_pairs(action, option_type):
    with pytest.raises(ValueError): make(action=action, option_type=option_type)


@pytest.mark.parametrize("option_type", ["CALL", "PUT"])
def test_wait_with_option_type_is_rejected(option_type):
    with pytest.raises(ValueError): blocked(action="WAIT", option_type=option_type)


def test_existing_blocked_incomplete_identity_remains_compatible_with_wait():
    value = blocked(action="WAIT", option_type=None, selection_id=None, trade_plan_id=None, contract_id=None, trading_symbol=None, expiry_date=None, strike=None, lot_size=None)
    assert value.to_dict()["action"] == "WAIT" and value.to_dict()["contract_id"] is None
