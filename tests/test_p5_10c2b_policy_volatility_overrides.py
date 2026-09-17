"""Focused P5-10C2B volatility-override policy coverage."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.contracts.market_regime_policy_v1 import (
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimePolicyV1,
)


DEFAULT_STATES = ("HIGH", "EXTREME")


def test_default_volatility_override_states_are_canonical_and_policy_is_frozen():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert policy.high_volatility_override_states == DEFAULT_STATES
    assert policy.high_volatility_state_values == DEFAULT_STATES
    assert policy.extreme_volatility_state_values == ("EXTREME",)
    with pytest.raises(FrozenInstanceError):
        policy.high_volatility_override_states = ()


def test_volatility_override_state_order_normalizes_without_mutating_caller_tuple():
    caller_states = ("EXTREME", "HIGH")
    policy = MarketRegimePolicyV1(high_volatility_override_states=caller_states)

    assert caller_states == ("EXTREME", "HIGH")
    assert policy.high_volatility_override_states == DEFAULT_STATES


@pytest.mark.parametrize(
    "invalid_states",
    [
        (),
        ("HIGH", "HIGH"),
        ("EXTREME", "EXTREME"),
        ("UNKNOWN",),
        ("LOW",),
        ("NORMAL",),
        ("UNAVAILABLE",),
        (1,),
        (True,),
        (None,),
        (("HIGH",),),
    ],
)
def test_volatility_override_state_members_are_controlled_exact_strings(invalid_states):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(high_volatility_override_states=invalid_states)


@pytest.mark.parametrize("invalid_states", [["HIGH"], {"HIGH"}, {"HIGH": True}, "HIGH", None])
def test_volatility_override_states_require_non_empty_tuple(invalid_states):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(high_volatility_override_states=invalid_states)


def test_volatility_override_serialization_is_deterministic_and_has_one_source():
    policy = MarketRegimePolicyV1(high_volatility_override_states=("EXTREME", "HIGH"))

    first_dict = policy.to_dict()
    first_json = policy.to_json()
    first_semantic = policy.semantic_dict()

    assert first_dict == policy.to_dict()
    assert first_json == policy.to_json()
    assert first_semantic == policy.semantic_dict()
    assert first_dict["high_volatility_override_states"] == DEFAULT_STATES
    assert "high_volatility_state_values" not in first_dict
    assert "extreme_volatility_state_values" not in first_dict
    assert first_json.count('"high_volatility_override_states"') == 1
    assert json.loads(first_json)["high_volatility_override_states"] == list(DEFAULT_STATES)


def test_volatility_compatibility_and_prior_policy_defaults_remain_unchanged():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert policy.high_volatility_confidence_penalty == 0.10
    assert policy.extreme_volatility_confidence_penalty == 0.25
    assert policy.required_components == ("TECHNICAL", "MARKET_SESSION")
    assert policy.optional_components == ("BROADER_MARKET", "EXTERNAL_CONTEXT")
    assert (policy.technical_weight, policy.broader_market_weight, policy.external_context_weight) == (0.60, 0.25, 0.15)
    assert dict(policy.maximum_component_age_seconds) == {
        "TECHNICAL": 300.0,
        "BROADER_MARKET": 600.0,
        "EXTERNAL_CONTEXT": 900.0,
        "MARKET_SESSION": 300.0,
    }
    assert policy.bullish_strength_threshold == 0.55
    assert policy.strong_bullish_strength_threshold == 0.75
    assert policy.conflict_penalty == 0.20


def test_broader_market_remains_volatility_authority_and_policy_has_no_evaluator_boundary():
    broader_result_source = Path(
        "services/contracts/broader_market_regime_component_result_v1.py"
    ).read_text(encoding="utf-8")
    broader_evaluator_source = Path("services/market_regime/broader.py").read_text(encoding="utf-8")
    technical_evaluator_source = Path("services/market_regime/technical.py").read_text(encoding="utf-8")
    policy_source = Path("services/contracts/market_regime_policy_v1.py").read_text(encoding="utf-8")

    assert "volatility_state" in broader_result_source
    assert "high_volatility_override_states" not in broader_evaluator_source
    assert "high_volatility_override_states" not in technical_evaluator_source
    forbidden = (
        "datetime.now",
        "date.today",
        "time.time",
        "uuid.uuid4",
        "requests",
        "socket",
        "def evaluate",
        "def classify",
        "vix",
        "indicator",
        "provider",
        "broker",
    )
    assert all(token not in policy_source.lower() for token in forbidden)


@pytest.mark.parametrize(
    "identity",
    (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")),
)
def test_default_volatility_policy_is_identity_neutral(identity):
    assert identity in DEFAULT_MARKET_REGIME_POLICY.required_components_by_identity
