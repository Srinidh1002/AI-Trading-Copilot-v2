from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from services.contracts.risk_policy_v1 import RiskPolicyV1


def make(**changes):
    values = dict(policy_id="risk-1", policy_name="Conservative", capital_base=100000.0, maximum_capital_per_trade=10000.0, maximum_capital_fraction=0.10, maximum_risk_per_trade=2000.0, maximum_risk_fraction=0.02, minimum_reward_risk_ratio=1.5, maximum_lots=10, maximum_quantity=500, allow_fractional_lots=False, require_stop_loss=True, require_target=True, require_positive_entry=True, require_positive_stop_loss=True, require_positive_target=True, require_stop_below_entry_for_long=True, require_target_above_entry_for_long=True, insufficient_capital_behavior="BLOCK")
    values.update(changes)
    return RiskPolicyV1(**values)


def test_valid_policy_is_immutable_and_slotted():
    value = make()
    assert value.schema_version == "risk_policy.v1" and not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError): value.policy_name = "changed"


@pytest.mark.parametrize("field,value", [("schema_version", "bad"), ("policy_id", ""), ("policy_name", " "), ("capital_base", 0), ("capital_base", -1), ("capital_base", float("nan")), ("capital_base", float("inf")), ("maximum_capital_per_trade", 100001), ("maximum_risk_per_trade", 100001), ("maximum_capital_fraction", 0), ("maximum_capital_fraction", 1.1), ("maximum_risk_fraction", -0.1), ("maximum_risk_fraction", float("inf")), ("minimum_reward_risk_ratio", 0), ("minimum_reward_risk_ratio", float("nan")), ("maximum_lots", 0), ("maximum_lots", -1), ("maximum_lots", True), ("maximum_quantity", 0), ("maximum_quantity", True), ("allow_fractional_lots", True), ("insufficient_capital_behavior", "PARTIAL")])
def test_invalid_constraints_are_rejected(field, value):
    with pytest.raises(ValueError): make(**{field: value})


@pytest.mark.parametrize("field", ["require_stop_loss", "require_target", "require_positive_entry", "require_positive_stop_loss", "require_positive_target", "require_stop_below_entry_for_long", "require_target_above_entry_for_long"])
def test_boolean_fields_reject_integer_impostors(field):
    with pytest.raises(ValueError): make(**{field: 1})


def test_metadata_is_defensively_copied_without_mutating_input():
    metadata = {"source": "manual"}; value = make(metadata=metadata); metadata["source"] = "changed"
    assert value.metadata == {"source": "manual"}


@pytest.mark.parametrize("metadata", [{"x": float("nan")}, {"x": float("inf")}, {"x": object()}])
def test_unsafe_metadata_is_rejected(metadata):
    with pytest.raises(ValueError): make(metadata=metadata)


def test_serialization_is_deterministic_and_primitive_only():
    value = make(metadata={"b": 2, "a": 1})
    assert value.to_dict() == value.to_dict() and value.to_json() == value.to_json()
    assert json.loads(value.to_json())["allow_fractional_lots"] is False


def test_semantic_dict_excludes_policy_id_and_is_deterministic():
    value = make()
    assert "policy_id" not in value.semantic_dict() and value.semantic_dict() == value.semantic_dict()


def test_equivalent_policies_compare_equal_and_constraints_change_semantics():
    assert make() == make() and make(maximum_lots=9).semantic_dict() != make().semantic_dict()


def test_round_trip_compatible_primitive_serialization():
    payload = json.loads(make().to_json())
    assert RiskPolicyV1(**payload) == make()
