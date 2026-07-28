import json

import pytest

from services.contracts.trade_opportunity_policy_v1 import (
    DEFAULT_TRADE_OPPORTUNITY_POLICY,
    TradeOpportunityPolicyV1,
)


def test_default_policy_is_valid():
    policy = TradeOpportunityPolicyV1()

    assert policy.schema_version == "trade_opportunity_policy.v1"
    assert policy.execution_mode == "PAPER"
    assert policy.live_execution_eligible is False
    assert sum(policy.weights.values()) == pytest.approx(1.0)
    assert policy.minimum_opportunity_score == 0.60


def test_default_singleton_matches_default_constructor():
    assert (
        DEFAULT_TRADE_OPPORTUNITY_POLICY.to_dict()
        == TradeOpportunityPolicyV1().to_dict()
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("technical_weight", -0.1),
        ("technical_weight", 1.1),
        ("option_chain_weight", -0.1),
        ("contract_ranking_weight", 1.1),
        ("decision_confidence_weight", -0.1),
        ("minimum_technical_strength", -0.1),
        ("minimum_technical_strength", 1.1),
        ("minimum_option_chain_strength", -0.1),
        ("minimum_contract_ranking_score", 1.1),
        ("minimum_decision_confidence", -0.1),
        ("minimum_opportunity_score", 1.1),
        ("maximum_source_age_seconds", 0),
        ("maximum_source_age_seconds", -1),
        ("maximum_future_skew_seconds", 0),
        ("maximum_future_skew_seconds", -1),
    ],
)
def test_invalid_numeric_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        TradeOpportunityPolicyV1(**{field: value})


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        TradeOpportunityPolicyV1(
            technical_weight=0.50,
        )


def test_custom_weights_are_exposed_deterministically():
    policy = TradeOpportunityPolicyV1(
        technical_weight=0.25,
        option_chain_weight=0.25,
        contract_ranking_weight=0.25,
        decision_confidence_weight=0.25,
    )

    assert policy.weights == {
        "technical": 0.25,
        "option_chain": 0.25,
        "contract_ranking": 0.25,
        "decision_confidence": 0.25,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision_policy", "UNKNOWN"),
        ("session_policy", "UNKNOWN"),
    ],
)
def test_invalid_policy_values(field, value):
    with pytest.raises(ValueError):
        TradeOpportunityPolicyV1(
            **{field: value}
        )


def test_policy_values_are_normalized():
    policy = TradeOpportunityPolicyV1(
        decision_policy="allow_analysis_only",
        session_policy="require_analysis_allowed",
    )

    assert policy.decision_policy == "ALLOW_ANALYSIS_ONLY"
    assert policy.session_policy == "REQUIRE_ANALYSIS_ALLOWED"


@pytest.mark.parametrize(
    "field",
    [
        "require_matching_direction",
        "require_ready_technical_intelligence",
        "require_ready_option_chain_intelligence",
        "require_ranked_contract",
    ],
)
def test_boolean_fields_require_boolean(field):
    with pytest.raises(TypeError):
        TradeOpportunityPolicyV1(
            **{field: 1}
        )


def test_metadata_is_copied_and_json_safe():
    metadata = {"source": "test"}
    policy = TradeOpportunityPolicyV1(
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
        TradeOpportunityPolicyV1(
            metadata={"bad": object()}
        )