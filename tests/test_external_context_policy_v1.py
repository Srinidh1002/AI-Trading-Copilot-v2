from dataclasses import FrozenInstanceError

import pytest

from services.contracts.external_context_policy_v1 import ExternalContextPolicyV1


def make(**changes):
    values = dict(
        required_observation_names={},
        optional_observation_names={},
        minimum_available_global_observations=0,
        minimum_global_confirmation_count=0,
    )
    values.update(changes)
    return ExternalContextPolicyV1(**values)


def test_valid_explicit_policy_is_frozen_and_deterministic():
    policy = make(metadata={"source": {"kind": "fixture"}})
    with pytest.raises(FrozenInstanceError):
        policy.policy_name = "changed"
    with pytest.raises(TypeError):
        policy.metadata["source"] = "changed"
    with pytest.raises(TypeError):
        policy.metadata["source"]["kind"] = "changed"
    assert policy.to_json() == policy.to_json()
    assert policy.semantic_dict() == policy.to_dict()


def test_required_optional_mappings_validate_identity_names_order_and_overlap():
    policy = make(
        required_observation_names={("NIFTY", "NSE"): ("GIFT_NIFTY",)},
        optional_observation_names={("NIFTY", "NSE"): ("SP500",)},
        minimum_available_global_observations=1,
        minimum_global_confirmation_count=1,
    )
    assert policy.required_observation_names[("NIFTY", "NSE")] == ("GIFT_NIFTY",)
    cases = (
        {"required_observation_names": {("NIFTY", "NSE"): ("UNKNOWN",)}},
        {"required_observation_names": {("NIFTY", "NSE"): ("SP500", "SP500")}},
        {"required_observation_names": {("NIFTY", "BSE"): ("SP500",)}},
        {"required_observation_names": {("NIFTY", "NSE"): ("SP500",)}, "optional_observation_names": {("NIFTY", "NSE"): ("SP500",)}},
    )
    for changes in cases:
        with pytest.raises(ValueError):
            make(**changes)


@pytest.mark.parametrize("field", ("maximum_observation_age_seconds", "event_lead_seconds_by_category", "event_cooldown_seconds_by_category"))
def test_nonnegative_mappings_reject_negative_and_nonfinite_values(field):
    with pytest.raises(ValueError):
        make(**{field: {"SP500" if "observation" in field else "CPI": -1}})
    with pytest.raises(ValueError):
        make(**{field: {"SP500" if "observation" in field else "CPI": float("inf")}})


def test_threshold_weights_and_component_consistency_validation():
    with pytest.raises(ValueError):
        make(flat_change_tolerance_percent=.2, minimum_directional_change_percent=.1)
    with pytest.raises(ValueError):
        make(observation_weights={"SP500": 0.9})
    with pytest.raises(ValueError):
        make(global_context_weight=.5, institutional_context_weight=.25, event_context_weight=.35)
    with pytest.raises(ValueError):
        make(require_global_context=True, minimum_available_component_count=0)
    with pytest.raises(TypeError):
        make(maximum_previous_session_age_days=1.0)


def test_event_and_execution_validation():
    with pytest.raises(ValueError):
        make(blocking_event_categories=("CPI",), warning_event_categories=("CPI",))
    with pytest.raises(ValueError):
        make(minimum_blocking_severity="LOW", minimum_warning_severity="HIGH")
    with pytest.raises(ValueError):
        make(execution_mode="LIVE")
    with pytest.raises(ValueError):
        make(live_execution_eligible=True)
