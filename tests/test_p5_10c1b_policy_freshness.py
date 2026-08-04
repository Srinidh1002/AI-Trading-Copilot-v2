"""Focused P5-10C1B freshness-policy contract coverage."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.contracts.market_regime_policy_v1 import (
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimePolicyV1,
)


CANONICAL_COMPONENTS = (
    "TECHNICAL",
    "BROADER_MARKET",
    "EXTERNAL_CONTEXT",
    "MARKET_SESSION",
)
DEFAULT_AGES = {
    "TECHNICAL": 300.0,
    "BROADER_MARKET": 600.0,
    "EXTERNAL_CONTEXT": 900.0,
    "MARKET_SESSION": 300.0,
}


def test_default_freshness_values_are_canonical_immutable_and_frozen():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert dict(policy.maximum_component_age_seconds) == DEFAULT_AGES
    assert tuple(policy.maximum_component_age_seconds) == CANONICAL_COMPONENTS
    assert all(isinstance(age, float) for age in policy.maximum_component_age_seconds.values())
    assert policy.future_timestamp_tolerance_seconds == 5.0
    assert policy.maximum_component_timestamp_skew_seconds == 900.0
    assert isinstance(policy.future_timestamp_tolerance_seconds, float)
    assert isinstance(policy.maximum_component_timestamp_skew_seconds, float)

    with pytest.raises(TypeError):
        policy.maximum_component_age_seconds["TECHNICAL"] = 1.0
    with pytest.raises(TypeError):
        del policy.maximum_component_age_seconds["TECHNICAL"]
    with pytest.raises(FrozenInstanceError):
        policy.maximum_component_age_seconds = {}


def test_age_mapping_is_copied_normalized_and_deterministic():
    caller_ages = {
        "MARKET_SESSION": 4,
        "EXTERNAL_CONTEXT": 3,
        "TECHNICAL": 1,
        "BROADER_MARKET": 2,
    }
    caller_snapshot = dict(caller_ages)

    first = MarketRegimePolicyV1(maximum_component_age_seconds=caller_ages)
    second = MarketRegimePolicyV1(maximum_component_age_seconds=caller_ages)

    assert tuple(first.maximum_component_age_seconds) == CANONICAL_COMPONENTS
    assert dict(first.maximum_component_age_seconds) == {
        "TECHNICAL": 1.0,
        "BROADER_MARKET": 2.0,
        "EXTERNAL_CONTEXT": 3.0,
        "MARKET_SESSION": 4.0,
    }
    assert caller_ages == caller_snapshot
    assert first.to_dict() == second.to_dict()

    caller_ages["TECHNICAL"] = 999
    assert first.maximum_component_age_seconds["TECHNICAL"] == 1.0


@pytest.mark.parametrize("invalid_ages", [[], (), set(), "ages", None, object()])
def test_age_mapping_requires_a_mapping(invalid_ages):
    with pytest.raises(TypeError):
        MarketRegimePolicyV1(maximum_component_age_seconds=invalid_ages)


@pytest.mark.parametrize(
    "invalid_ages",
    [
        {key: value for key, value in DEFAULT_AGES.items() if key != "TECHNICAL"},
        {key: value for key, value in DEFAULT_AGES.items() if key != "BROADER_MARKET"},
        {key: value for key, value in DEFAULT_AGES.items() if key != "EXTERNAL_CONTEXT"},
        {key: value for key, value in DEFAULT_AGES.items() if key != "MARKET_SESSION"},
        {**DEFAULT_AGES, "UNKNOWN": 1.0},
        {**DEFAULT_AGES, 1: 1.0},
        {**DEFAULT_AGES, True: 1.0},
        {**DEFAULT_AGES, None: 1.0},
        {**DEFAULT_AGES, ("TECHNICAL",): 1.0},
    ],
)
def test_age_mapping_requires_exact_controlled_string_keys(invalid_ages):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(maximum_component_age_seconds=invalid_ages)


@pytest.mark.parametrize(
    "invalid_value",
    [0, 0.0, -1, -0.5, True, False, None, "300", float("nan"), float("inf"), float("-inf")],
)
@pytest.mark.parametrize("component", CANONICAL_COMPONENTS)
def test_component_ages_reject_invalid_values(component, invalid_value):
    ages = dict(DEFAULT_AGES)
    ages[component] = invalid_value

    with pytest.raises(ValueError):
        MarketRegimePolicyV1(maximum_component_age_seconds=ages)


@pytest.mark.parametrize("valid_value", [1, 0.25, 1e-12, 1e20])
@pytest.mark.parametrize("component", CANONICAL_COMPONENTS)
def test_component_ages_accept_positive_finite_numbers(component, valid_value):
    ages = dict(DEFAULT_AGES)
    ages[component] = valid_value

    policy = MarketRegimePolicyV1(maximum_component_age_seconds=ages)
    assert policy.maximum_component_age_seconds[component] == float(valid_value)
    assert isinstance(policy.maximum_component_age_seconds[component], float)


@pytest.mark.parametrize(
    "field",
    ("future_timestamp_tolerance_seconds", "maximum_component_timestamp_skew_seconds"),
)
@pytest.mark.parametrize(
    "invalid_value",
    [-1, -0.5, True, False, None, "5", float("nan"), float("inf"), float("-inf")],
)
def test_freshness_tolerances_reject_invalid_values(field, invalid_value):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(**{field: invalid_value})


@pytest.mark.parametrize(
    "field",
    ("future_timestamp_tolerance_seconds", "maximum_component_timestamp_skew_seconds"),
)
@pytest.mark.parametrize("valid_value", [0, 2, 0.125])
def test_freshness_tolerances_accept_non_negative_finite_numbers(field, valid_value):
    policy = MarketRegimePolicyV1(**{field: valid_value})
    assert getattr(policy, field) == float(valid_value)
    assert isinstance(getattr(policy, field), float)


def test_freshness_serialization_is_deterministic_json_safe_and_non_mutating():
    caller_ages = {
        "MARKET_SESSION": 40,
        "EXTERNAL_CONTEXT": 30,
        "BROADER_MARKET": 20,
        "TECHNICAL": 10,
    }
    policy = MarketRegimePolicyV1(
        maximum_component_age_seconds=caller_ages,
        future_timestamp_tolerance_seconds=1,
        maximum_component_timestamp_skew_seconds=2.5,
    )

    first_dict = policy.to_dict()
    first_json = policy.to_json()
    first_semantic = policy.semantic_dict()

    assert first_dict == policy.to_dict()
    assert first_json == policy.to_json()
    assert first_semantic == policy.semantic_dict()
    assert tuple(first_dict["maximum_component_age_seconds"]) == CANONICAL_COMPONENTS
    assert first_dict["maximum_component_age_seconds"] == {
        "TECHNICAL": 10.0,
        "BROADER_MARKET": 20.0,
        "EXTERNAL_CONTEXT": 30.0,
        "MARKET_SESSION": 40.0,
    }
    assert first_dict["future_timestamp_tolerance_seconds"] == 1.0
    assert first_dict["maximum_component_timestamp_skew_seconds"] == 2.5
    assert first_json.count('"maximum_component_age_seconds"') == 1
    parsed = json.loads(first_json)
    assert parsed["maximum_component_age_seconds"] == first_dict["maximum_component_age_seconds"]
    assert parsed["future_timestamp_tolerance_seconds"] == 1.0
    assert parsed["maximum_component_timestamp_skew_seconds"] == 2.5

    caller_ages["TECHNICAL"] = 999
    assert policy.maximum_component_age_seconds["TECHNICAL"] == 10.0
    assert policy.to_dict() == first_dict


def test_compatibility_fields_and_p5_10c1a_defaults_remain_available():
    policy = DEFAULT_MARKET_REGIME_POLICY

    for field in (
        "maximum_component_age_seconds",
        "future_timestamp_tolerance_seconds",
        "maximum_component_timestamp_skew_seconds",
    ):
        assert hasattr(policy, field)
    assert policy.required_components == ("TECHNICAL", "MARKET_SESSION")
    assert policy.optional_components == ("BROADER_MARKET", "EXTERNAL_CONTEXT")
    assert policy.technical_weight == 0.60
    assert policy.broader_market_weight == 0.25
    assert policy.external_context_weight == 0.15


def test_policy_source_has_no_freshness_evaluation_or_external_boundary_calls():
    source = Path("services/contracts/market_regime_policy_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "datetime.now",
        "date.today",
        "time.time",
        "uuid.uuid4",
        "random",
        "requests",
        "socket",
        "provider initialization",
        "broker initialization",
    )

    assert all(token not in source for token in forbidden)
