from dataclasses import FrozenInstanceError, replace
import json

import pytest

from services.contracts.option_chain_policy_v1 import (
    DEFAULT_OPTION_CHAIN_POLICY,
    OptionChainPolicyV1,
)
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES


def policy(**changes):
    values = {
        "policy_name": "fixture-policy", "supported_markets": SUPPORTED_MARKET_IDENTITIES,
        "maximum_age_seconds": 300.0, "future_tolerance_seconds": 5.0,
        "minimum_total_strikes": 10, "minimum_complete_pairs": 5,
        "minimum_completeness_ratio": 0.50, "incomplete_behavior": "BLOCK",
        "missing_side_behavior": "WARN", "crossed_market_behavior": "BLOCK",
        "duplicate_strike_behavior": "BLOCK",
    }
    values.update(changes)
    return OptionChainPolicyV1(**values)


def test_default_policy_has_exact_initial_architectural_values():
    value = DEFAULT_OPTION_CHAIN_POLICY
    assert value.policy_name == "INITIAL_CANONICAL_OPTION_CHAIN_POLICY"
    assert value.supported_markets == SUPPORTED_MARKET_IDENTITIES
    assert (value.maximum_age_seconds, value.future_tolerance_seconds) == (300.0, 5.0)
    assert (value.minimum_total_strikes, value.minimum_complete_pairs, value.minimum_completeness_ratio) == (10, 5, 0.50)
    assert (value.incomplete_behavior, value.missing_side_behavior, value.crossed_market_behavior, value.duplicate_strike_behavior) == ("BLOCK", "WARN", "BLOCK", "BLOCK")


def test_policy_serialization_is_primitive_and_deterministic():
    data = DEFAULT_OPTION_CHAIN_POLICY.to_dict()
    assert data["schema_version"] == "option_chain_policy.v1"
    assert data["supported_markets"] == [["NIFTY", "NSE"], ["BANKNIFTY", "NSE"], ["FINNIFTY", "NSE"], ["SENSEX", "BSE"]]
    assert json.loads(json.dumps(data, sort_keys=True, allow_nan=False)) == data


def test_policy_is_frozen_and_slotted():
    with pytest.raises(FrozenInstanceError):
        DEFAULT_OPTION_CHAIN_POLICY.maximum_age_seconds = 1.0
    with pytest.raises((AttributeError, TypeError)):
        DEFAULT_OPTION_CHAIN_POLICY.unexpected = "no"


@pytest.mark.parametrize(
    "markets",
    (
        (),
        (("NIFTY", "NSE"),),
        tuple(reversed(SUPPORTED_MARKET_IDENTITIES)),
        (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "NSE")),
        (("NIFTY50", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")),
        [*SUPPORTED_MARKET_IDENTITIES],
    ),
)
def test_supported_markets_must_be_exact_four_market_tuple(markets):
    with pytest.raises(ValueError):
        policy(supported_markets=markets)


@pytest.mark.parametrize("value", ("", " ", 1, None))
def test_policy_name_must_be_nonempty_text(value):
    with pytest.raises(ValueError):
        policy(policy_name=value)


@pytest.mark.parametrize("field", ("maximum_age_seconds",))
@pytest.mark.parametrize("value", (0, -1, True, float("nan"), float("inf")))
def test_maximum_age_must_be_positive_finite(field, value):
    with pytest.raises(ValueError):
        policy(**{field: value})


@pytest.mark.parametrize("value", (-1, True, float("nan"), float("inf"), "5"))
def test_future_tolerance_must_be_nonnegative_finite(value):
    with pytest.raises(ValueError):
        policy(future_tolerance_seconds=value)


@pytest.mark.parametrize("field", ("minimum_total_strikes", "minimum_complete_pairs"))
@pytest.mark.parametrize("value", (-1, 1.5, True, "5"))
def test_minimum_counts_must_be_nonnegative_integers(field, value):
    with pytest.raises(ValueError):
        policy(**{field: value})


@pytest.mark.parametrize("value", (-0.01, 1.01, True, float("nan"), float("inf"), "0.5"))
def test_minimum_completeness_ratio_is_bounded_finite(value):
    with pytest.raises(ValueError):
        policy(minimum_completeness_ratio=value)


@pytest.mark.parametrize(
    "field",
    ("incomplete_behavior", "missing_side_behavior", "crossed_market_behavior", "duplicate_strike_behavior"),
)
@pytest.mark.parametrize("behavior", ("BLOCK", "WARN", "ALLOW"))
def test_all_controlled_policy_behaviors_are_available(field, behavior):
    assert policy(**{field: behavior}).__getattribute__(field) == behavior


@pytest.mark.parametrize(
    "field",
    ("incomplete_behavior", "missing_side_behavior", "crossed_market_behavior", "duplicate_strike_behavior"),
)
@pytest.mark.parametrize("behavior", ("IGNORE", "block", "", None, True))
def test_policy_behavior_values_are_controlled(field, behavior):
    with pytest.raises(ValueError):
        policy(**{field: behavior})


@pytest.mark.parametrize(
    "changes",
    (
        {"execution_mode": "LIVE"},
        {"execution_mode": ""},
        {"live_execution_eligible": True},
        {"schema_version": "option_chain_policy.v2"},
    ),
)
def test_policy_is_paper_only_and_schema_versioned(changes):
    with pytest.raises(ValueError):
        policy(**changes)


def test_replace_keeps_valid_policy_configuration():
    changed = replace(DEFAULT_OPTION_CHAIN_POLICY, policy_name="other-policy", maximum_age_seconds=60.0, missing_side_behavior="ALLOW")
    assert (changed.policy_name, changed.maximum_age_seconds, changed.missing_side_behavior) == ("other-policy", 60.0, "ALLOW")
