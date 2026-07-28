import json

import pytest

from services.contracts.option_contract_ranking_policy_v1 import (
    DEFAULT_OPTION_CONTRACT_RANKING_POLICY,
    OptionContractRankingPolicyV1,
)


def test_default_policy_is_valid():
    policy = OptionContractRankingPolicyV1()

    assert policy.schema_version == (
        "option_contract_ranking_policy.v1"
    )
    assert policy.execution_mode == "PAPER"
    assert policy.live_execution_eligible is False
    assert sum(policy.weights.values()) == pytest.approx(1.0)
    assert policy.maximum_ranked_candidates == 10


def test_default_singleton_matches_default_constructor():
    assert (
        DEFAULT_OPTION_CONTRACT_RANKING_POLICY.to_dict()
        == OptionContractRankingPolicyV1().to_dict()
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_universe_age_seconds", 0),
        ("maximum_universe_age_seconds", -1),
        ("maximum_contract_age_seconds", 0),
        ("maximum_contract_age_seconds", -1),
        ("maximum_future_skew_seconds", -1),
        ("maximum_spread_percent", 0),
        ("maximum_spread_percent", -1),
        ("minimum_volume", -1),
        ("minimum_open_interest", -1),
        ("minimum_implied_volatility", -1),
        ("maximum_implied_volatility", -1),
        ("maximum_strike_distance_percent", 0),
        ("maximum_strike_distance_percent", -1),
        ("maximum_ranked_candidates", 0),
        ("maximum_ranked_candidates", -1),
        ("maximum_ranked_candidates", True),
    ],
)
def test_invalid_numeric_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        OptionContractRankingPolicyV1(
            **{field: value}
        )


@pytest.mark.parametrize(
    "field",
    [
        "require_trusted_universe",
        "require_bid_ask",
        "require_volume",
        "require_open_interest",
        "require_implied_volatility",
    ],
)
def test_boolean_fields_require_boolean(field):
    with pytest.raises(TypeError):
        OptionContractRankingPolicyV1(
            **{field: 1}
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("expiry_policy", "UNKNOWN"),
        ("intelligence_policy", "UNKNOWN"),
        ("reference_price_policy", "UNKNOWN"),
    ],
)
def test_invalid_policy_enums(field, value):
    with pytest.raises(ValueError):
        OptionContractRankingPolicyV1(
            **{field: value}
        )


def test_policy_values_are_normalized():
    policy = OptionContractRankingPolicyV1(
        expiry_policy="all_eligible",
        intelligence_policy="ignore",
        reference_price_policy="mid",
    )

    assert policy.expiry_policy == "ALL_ELIGIBLE"
    assert policy.intelligence_policy == "IGNORE"
    assert policy.reference_price_policy == "MID"


def test_iv_range_must_be_consistent():
    with pytest.raises(ValueError):
        OptionContractRankingPolicyV1(
            minimum_implied_volatility=50,
            maximum_implied_volatility=20,
        )


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        OptionContractRankingPolicyV1(
            liquidity_weight=0.50,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("liquidity_weight", -0.1),
        ("liquidity_weight", 1.1),
        ("proximity_weight", -0.1),
        ("intelligence_alignment_weight", 1.1),
    ],
)
def test_weights_must_be_unit_interval(field, value):
    with pytest.raises(ValueError):
        OptionContractRankingPolicyV1(
            **{field: value}
        )


def test_custom_weights_are_exposed_deterministically():
    policy = OptionContractRankingPolicyV1(
        liquidity_weight=0.20,
        proximity_weight=0.20,
        open_interest_weight=0.15,
        volume_weight=0.15,
        spread_weight=0.10,
        implied_volatility_weight=0.10,
        intelligence_alignment_weight=0.10,
    )

    assert policy.weights == {
        "liquidity": 0.20,
        "proximity": 0.20,
        "open_interest": 0.15,
        "volume": 0.15,
        "spread": 0.10,
        "implied_volatility": 0.10,
        "intelligence_alignment": 0.10,
    }


def test_metadata_is_copied_and_json_safe():
    metadata = {"source": "test"}
    policy = OptionContractRankingPolicyV1(
        metadata=metadata
    )
    metadata["source"] = "changed"

    assert policy.metadata == {"source": "test"}
    assert json.dumps(
        policy.to_dict(),
        allow_nan=False,
    )


def test_unsafe_metadata_is_rejected():
    with pytest.raises(ValueError):
        OptionContractRankingPolicyV1(
            metadata={"bad": object()}
        )