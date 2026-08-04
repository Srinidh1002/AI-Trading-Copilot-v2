"""Focused P5-10C2A policy threshold and aggregate-penalty coverage."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.contracts.market_regime_policy_v1 import (
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimePolicyV1,
)


STRENGTH_FIELDS = (
    "bullish_strength_threshold",
    "strong_bullish_strength_threshold",
    "bearish_strength_threshold",
    "strong_bearish_strength_threshold",
)
CONFIDENCE_FIELDS = (
    "minimum_regime_confidence",
    "strong_regime_confidence_threshold",
)
SUITABILITY_FIELDS = (
    "caution_confidence_threshold",
    "suitable_confidence_threshold",
)
PENALTY_FIELDS = (
    "conflict_penalty",
    "missing_optional_component_penalty",
    "warning_penalty",
    "partial_confirmation_penalty",
)
INVALID_UNIT_VALUES = (-0.1, 1.1, True, False, None, "0.5", float("nan"), float("inf"), float("-inf"))


def test_c2a_defaults_are_exact_and_normalized():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert {
        field: getattr(policy, field)
        for field in STRENGTH_FIELDS
    } == {
        "bullish_strength_threshold": 0.55,
        "strong_bullish_strength_threshold": 0.75,
        "bearish_strength_threshold": 0.55,
        "strong_bearish_strength_threshold": 0.75,
    }
    assert {
        field: getattr(policy, field)
        for field in CONFIDENCE_FIELDS
    } == {
        "minimum_regime_confidence": 0.50,
        "strong_regime_confidence_threshold": 0.75,
    }
    assert {
        field: getattr(policy, field)
        for field in SUITABILITY_FIELDS
    } == {
        "caution_confidence_threshold": 0.50,
        "suitable_confidence_threshold": 0.70,
    }
    assert policy.minimum_confirmation_count == 1
    assert {
        field: getattr(policy, field)
        for field in PENALTY_FIELDS
    } == {
        "conflict_penalty": 0.20,
        "missing_optional_component_penalty": 0.05,
        "warning_penalty": 0.05,
        "partial_confirmation_penalty": 0.10,
    }
    assert all(isinstance(getattr(policy, field), float) for field in STRENGTH_FIELDS + CONFIDENCE_FIELDS + SUITABILITY_FIELDS + PENALTY_FIELDS)
    assert type(policy.minimum_confirmation_count) is int


@pytest.mark.parametrize("field", STRENGTH_FIELDS + CONFIDENCE_FIELDS + SUITABILITY_FIELDS + PENALTY_FIELDS)
@pytest.mark.parametrize("invalid_value", INVALID_UNIT_VALUES)
def test_bounded_thresholds_and_penalties_reject_invalid_values(field, invalid_value):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(**{field: invalid_value})


@pytest.mark.parametrize("value", (0, 1, 0.375))
def test_strength_thresholds_accept_bounded_numbers_and_store_floats(value):
    policy = MarketRegimePolicyV1(
        bullish_strength_threshold=value,
        strong_bullish_strength_threshold=value,
        bearish_strength_threshold=value,
        strong_bearish_strength_threshold=value,
    )

    assert all(getattr(policy, field) == float(value) for field in STRENGTH_FIELDS)
    assert all(isinstance(getattr(policy, field), float) for field in STRENGTH_FIELDS)


@pytest.mark.parametrize("value", (0, 1, 0.375))
def test_confidence_thresholds_accept_bounded_numbers_and_store_floats(value):
    policy = MarketRegimePolicyV1(
        minimum_regime_confidence=value,
        strong_regime_confidence_threshold=value,
    )

    assert all(getattr(policy, field) == float(value) for field in CONFIDENCE_FIELDS)
    assert all(isinstance(getattr(policy, field), float) for field in CONFIDENCE_FIELDS)


@pytest.mark.parametrize("value", (0, 1, 0.375))
def test_suitability_thresholds_accept_bounded_numbers_and_store_floats(value):
    policy = MarketRegimePolicyV1(
        caution_confidence_threshold=value,
        suitable_confidence_threshold=value,
    )

    assert all(getattr(policy, field) == float(value) for field in SUITABILITY_FIELDS)
    assert all(isinstance(getattr(policy, field), float) for field in SUITABILITY_FIELDS)


def test_strength_threshold_ordering_allows_equal_and_rejects_weaker_strong_values():
    equal = MarketRegimePolicyV1(
        bullish_strength_threshold=0.6,
        strong_bullish_strength_threshold=0.6,
        bearish_strength_threshold=0.7,
        strong_bearish_strength_threshold=0.7,
    )
    assert equal.strong_bullish_strength_threshold == equal.bullish_strength_threshold
    assert equal.strong_bearish_strength_threshold == equal.bearish_strength_threshold

    with pytest.raises(ValueError):
        MarketRegimePolicyV1(bullish_strength_threshold=0.6, strong_bullish_strength_threshold=0.5)
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(bearish_strength_threshold=0.6, strong_bearish_strength_threshold=0.5)


def test_confidence_and_suitability_ordering_allows_equal_and_rejects_reversal():
    equal = MarketRegimePolicyV1(
        minimum_regime_confidence=0.6,
        strong_regime_confidence_threshold=0.6,
        caution_confidence_threshold=0.7,
        suitable_confidence_threshold=0.7,
    )
    assert equal.strong_regime_confidence_threshold == equal.minimum_regime_confidence
    assert equal.suitable_confidence_threshold == equal.caution_confidence_threshold

    with pytest.raises(ValueError):
        MarketRegimePolicyV1(minimum_regime_confidence=0.6, strong_regime_confidence_threshold=0.5)
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(caution_confidence_threshold=0.6, suitable_confidence_threshold=0.5)


@pytest.mark.parametrize("value", (0, 1, 0.375))
@pytest.mark.parametrize("field", PENALTY_FIELDS)
def test_aggregate_penalties_accept_bounded_numbers_and_remain_distinct(field, value):
    policy = MarketRegimePolicyV1(**{field: value})

    assert getattr(policy, field) == float(value)
    assert isinstance(getattr(policy, field), float)
    if field == "conflict_penalty":
        assert policy.conflict_penalty == float(value)
    else:
        assert policy.conflict_penalty == 0.20


@pytest.mark.parametrize("value", (0, 3))
def test_minimum_confirmation_count_accepts_non_negative_exact_integers(value):
    policy = MarketRegimePolicyV1(minimum_confirmation_count=value)
    assert policy.minimum_confirmation_count == value
    assert type(policy.minimum_confirmation_count) is int


@pytest.mark.parametrize("invalid_value", (-1, True, False, 1.0, "1", None))
def test_minimum_confirmation_count_rejects_non_integer_or_negative_values(invalid_value):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(minimum_confirmation_count=invalid_value)


def test_compatibility_fields_c1a_and_c1b_defaults_and_freezing_remain_intact():
    policy = DEFAULT_MARKET_REGIME_POLICY

    for field in (
        "range_bound_strength_max",
        "directional_strength_min",
        "strong_directional_strength_min",
        "confirmation_strength_threshold",
        "partial_confirmation_strength_threshold",
        "technical_conflict_penalty",
        "broader_market_conflict_penalty",
        "external_context_conflict_penalty",
        "partial_evidence_penalty",
    ):
        assert hasattr(policy, field)
    assert policy.conflict_penalty != policy.technical_conflict_penalty or policy.conflict_penalty == 0.20
    assert policy.required_components == ("TECHNICAL", "MARKET_SESSION")
    assert policy.optional_components == ("BROADER_MARKET", "EXTERNAL_CONTEXT")
    assert (policy.technical_weight, policy.broader_market_weight, policy.external_context_weight) == (0.60, 0.25, 0.15)
    assert dict(policy.maximum_component_age_seconds) == {
        "TECHNICAL": 300.0,
        "BROADER_MARKET": 600.0,
        "EXTERNAL_CONTEXT": 900.0,
        "MARKET_SESSION": 300.0,
    }
    with pytest.raises(FrozenInstanceError):
        policy.conflict_penalty = 0.1


def test_serialization_is_deterministic_and_has_one_canonical_source_per_field():
    policy = MarketRegimePolicyV1(
        bullish_strength_threshold=0,
        strong_bullish_strength_threshold=1,
        bearish_strength_threshold=0.25,
        strong_bearish_strength_threshold=0.75,
        minimum_regime_confidence=0.25,
        strong_regime_confidence_threshold=0.75,
        caution_confidence_threshold=0.25,
        suitable_confidence_threshold=0.75,
        minimum_confirmation_count=2,
        conflict_penalty=0.1,
        warning_penalty=0.2,
        partial_confirmation_penalty=0.3,
    )

    first_dict = policy.to_dict()
    first_json = policy.to_json()
    first_semantic = policy.semantic_dict()

    assert first_dict == policy.to_dict()
    assert first_json == policy.to_json()
    assert first_semantic == policy.semantic_dict()
    for field in STRENGTH_FIELDS + CONFIDENCE_FIELDS + SUITABILITY_FIELDS + PENALTY_FIELDS:
        assert field in first_dict
        assert isinstance(first_dict[field], float)
        assert first_json.count(f'"{field}"') == 1
    assert first_dict["minimum_confirmation_count"] == 2
    assert type(first_dict["minimum_confirmation_count"]) is int
    assert json.loads(first_json)["partial_confirmation_penalty"] == 0.3


def test_policy_stores_thresholds_only_without_runtime_or_classification_boundaries():
    source = Path("services/contracts/market_regime_policy_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "datetime.now",
        "date.today",
        "time.time",
        "uuid.uuid4",
        "requests",
        "socket",
        "provider",
        "broker",
        "def evaluate",
        "def classify",
        "strategy",
        "strike",
        "expiry",
    )

    assert all(token not in source for token in forbidden)


@pytest.mark.parametrize("identity", (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")))
def test_default_policy_is_identity_neutral_and_reusable_for_all_supported_markets(identity):
    assert identity in DEFAULT_MARKET_REGIME_POLICY.required_components_by_identity
