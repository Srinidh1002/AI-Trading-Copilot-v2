"""Focused P5-10C2C event, session, and precedence policy coverage."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.contracts.market_regime_policy_v1 import (
    DEFAULT_MARKET_REGIME_POLICY,
    MarketRegimePolicyV1,
)


EVENT_ORDER = ("NONE", "LOW", "MODERATE", "HIGH", "EXTREME", "UNAVAILABLE")
PRECEDENCE = ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL")
BOOL_FIELDS = (
    "block_when_analysis_disallowed",
    "preserve_session_owned_restriction",
    "use_most_restrictive_entry_policy",
    "block_on_required_component_failure",
    "warn_on_optional_component_failure",
)


def test_event_session_and_precedence_defaults_are_exact_and_immutable():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert policy.event_risk_override_states == ("HIGH", "EXTREME")
    assert policy.blocking_event_risk_states == ("EXTREME",)
    assert all(getattr(policy, field) is True for field in BOOL_FIELDS)
    assert policy.aggregate_status_precedence == PRECEDENCE
    with pytest.raises(FrozenInstanceError):
        policy.block_when_analysis_disallowed = False


def test_event_state_tuples_normalize_without_mutating_callers():
    override_states = ("EXTREME", "HIGH", "MODERATE")
    blocking_states = ("EXTREME", "HIGH")
    policy = MarketRegimePolicyV1(
        event_risk_override_states=override_states,
        blocking_event_risk_states=blocking_states,
    )

    assert override_states == ("EXTREME", "HIGH", "MODERATE")
    assert blocking_states == ("EXTREME", "HIGH")
    assert policy.event_risk_override_states == ("MODERATE", "HIGH", "EXTREME")
    assert policy.blocking_event_risk_states == ("HIGH", "EXTREME")


@pytest.mark.parametrize(
    "invalid_states",
    [
        (),
        ("HIGH", "HIGH"),
        ("NONE",),
        ("UNAVAILABLE",),
        ("UNKNOWN",),
        (1,),
        (True,),
        (None,),
        (("HIGH",),),
        ["HIGH"],
        {"HIGH"},
        {"HIGH": True},
        "HIGH",
        None,
    ],
)
def test_event_override_states_reject_invalid_members_and_containers(invalid_states):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(event_risk_override_states=invalid_states)


@pytest.mark.parametrize(
    "invalid_states",
    [
        (),
        ("EXTREME", "EXTREME"),
        ("NONE",),
        ("UNAVAILABLE",),
        ("UNKNOWN",),
        ("LOW",),
        (1,),
        (True,),
        (None,),
        (("HIGH",),),
        ["EXTREME"],
        {"EXTREME"},
        {"EXTREME": True},
        "EXTREME",
        None,
    ],
)
def test_blocking_event_states_reject_invalid_or_non_override_values(invalid_states):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(blocking_event_risk_states=invalid_states)


def test_blocking_event_states_must_be_subset_of_override_states():
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(
            event_risk_override_states=("MODERATE",),
            blocking_event_risk_states=("HIGH",),
        )


@pytest.mark.parametrize("field", BOOL_FIELDS)
@pytest.mark.parametrize("invalid_value", (0, 1, "true", None, [], {}, object()))
def test_session_and_fail_closed_flags_require_exact_bool(field, invalid_value):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(**{field: invalid_value})


@pytest.mark.parametrize("field", BOOL_FIELDS)
@pytest.mark.parametrize("value", (True, False))
def test_session_and_fail_closed_flags_accept_exact_bool(field, value):
    policy = MarketRegimePolicyV1(**{field: value})
    assert getattr(policy, field) is value


def test_precedence_is_locked_to_the_required_complete_order():
    policy = DEFAULT_MARKET_REGIME_POLICY

    assert policy.aggregate_status_precedence == PRECEDENCE
    assert len(policy.aggregate_status_precedence) == len(set(policy.aggregate_status_precedence)) == 6
    assert policy.aggregate_status_precedence[0] == "BLOCKED"
    assert policy.aggregate_status_precedence[-1] == "DIRECTIONAL"


@pytest.mark.parametrize(
    "invalid_precedence",
    [
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "UNKNOWN"),
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "UNAVAILABLE"),
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE"),
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", 1),
        ["BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL"],
        {"BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL"},
        {"BLOCKED": True},
        "BLOCKED",
        None,
        ("EVENT_RISK", "BLOCKED", "CONFLICTING", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL"),
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "HIGH_VOLATILITY", "DIRECTIONAL", "UNAVAILABLE"),
        ("BLOCKED", "CONFLICTING", "EVENT_RISK", "HIGH_VOLATILITY", "UNAVAILABLE", "DIRECTIONAL"),
        ("BLOCKED", "EVENT_RISK", "HIGH_VOLATILITY", "CONFLICTING", "UNAVAILABLE", "DIRECTIONAL"),
        ("BLOCKED", "EVENT_RISK", "CONFLICTING", "UNAVAILABLE", "HIGH_VOLATILITY", "DIRECTIONAL"),
    ],
)
def test_precedence_rejects_invalid_containers_members_and_ordering(invalid_precedence):
    with pytest.raises(ValueError):
        MarketRegimePolicyV1(aggregate_status_precedence=invalid_precedence)


def test_event_session_serialization_is_deterministic_and_json_safe():
    policy = MarketRegimePolicyV1(
        event_risk_override_states=("EXTREME", "HIGH"),
        blocking_event_risk_states=("EXTREME",),
        block_when_analysis_disallowed=False,
        preserve_session_owned_restriction=False,
        use_most_restrictive_entry_policy=False,
        block_on_required_component_failure=False,
        warn_on_optional_component_failure=False,
    )

    first_dict = policy.to_dict()
    first_json = policy.to_json()
    first_semantic = policy.semantic_dict()

    assert first_dict == policy.to_dict()
    assert first_json == policy.to_json()
    assert first_semantic == policy.semantic_dict()
    assert first_dict["event_risk_override_states"] == ("HIGH", "EXTREME")
    assert first_dict["blocking_event_risk_states"] == ("EXTREME",)
    assert first_dict["aggregate_status_precedence"] == PRECEDENCE
    assert all(first_dict[field] is False for field in BOOL_FIELDS)
    for field in ("event_risk_override_states", "blocking_event_risk_states", "aggregate_status_precedence"):
        assert first_json.count(f'"{field}"') == 1
    parsed = json.loads(first_json)
    assert parsed["event_risk_override_states"] == ["HIGH", "EXTREME"]
    assert parsed["aggregate_status_precedence"] == list(PRECEDENCE)
    assert all(parsed[field] is False for field in BOOL_FIELDS)


def test_compatibility_prior_defaults_and_boundary_ownership_remain_intact():
    policy = DEFAULT_MARKET_REGIME_POLICY
    external_source = Path("services/market_regime/external.py").read_text(encoding="utf-8")
    technical_source = Path("services/market_regime/technical.py").read_text(encoding="utf-8")
    broader_source = Path("services/market_regime/broader.py").read_text(encoding="utf-8")
    policy_source = Path("services/contracts/market_regime_policy_v1.py").read_text(encoding="utf-8").lower()

    assert "entry_restriction_state" in external_source
    assert "event_risk_override_states" not in external_source
    assert "aggregate_status_precedence" not in technical_source
    assert "aggregate_status_precedence" not in broader_source
    assert policy.required_components == ("TECHNICAL", "MARKET_SESSION")
    assert policy.optional_components == ("BROADER_MARKET", "EXTERNAL_CONTEXT")
    assert (policy.technical_weight, policy.broader_market_weight, policy.external_context_weight) == (0.60, 0.25, 0.15)
    assert policy.future_timestamp_tolerance_seconds == 5.0
    assert policy.bullish_strength_threshold == 0.55
    assert policy.high_volatility_override_states == ("HIGH", "EXTREME")
    assert all(token not in policy_source for token in (
        "datetime.now", "date.today", "time.time", "uuid.uuid4", "requests", "socket",
        "def evaluate", "def classify", "holiday", "calendar", "authorize_execution",
    ))


@pytest.mark.parametrize(
    "identity",
    (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")),
)
def test_default_event_session_policy_is_identity_neutral(identity):
    assert identity in DEFAULT_MARKET_REGIME_POLICY.required_components_by_identity
