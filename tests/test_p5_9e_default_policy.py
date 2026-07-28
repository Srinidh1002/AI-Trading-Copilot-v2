from services.contracts import DEFAULT_EXTERNAL_CONTEXT_POLICY, ExternalContextPolicyV1


def test_default_policy_is_constructed_and_lazy_exported():
    assert isinstance(DEFAULT_EXTERNAL_CONTEXT_POLICY, ExternalContextPolicyV1)
    assert DEFAULT_EXTERNAL_CONTEXT_POLICY.required_observation_names == {}
    assert DEFAULT_EXTERNAL_CONTEXT_POLICY.minimum_available_component_count == 0


def test_default_global_institutional_and_event_behavior_is_conservative():
    policy = DEFAULT_EXTERNAL_CONTEXT_POLICY
    assert policy.warn_on_missing_optional_observation
    assert policy.warn_on_stale_optional_observation
    assert policy.allow_delayed_optional_observations
    assert not policy.require_institutional_flow
    assert policy.allow_provisional_institutional_flow
    assert policy.previous_session_flow_allowed
    assert policy.block_new_entries_for_active_events
    assert policy.allow_analysis_during_entry_block
    assert policy.event_block_precedence
    assert policy.holiday_event_owned_by_session_validation
    assert policy.special_session_owned_by_session_validation
    assert policy.expiry_event_is_context_only and policy.rollover_event_is_context_only


def test_default_weight_rules_are_exact_and_correlated_groups_are_capped():
    policy = DEFAULT_EXTERNAL_CONTEXT_POLICY
    assert sum(policy.observation_weights.values()) == 1.0
    assert sum((policy.global_context_weight, policy.institutional_context_weight, policy.event_context_weight)) == 1.0
    assert sum(policy.observation_weights[name] for name in ("SP500", "NASDAQ", "DOW_JONES")) < .25
    assert sum(policy.observation_weights[name] for name in ("BRENT_CRUDE", "WTI_CRUDE")) < .15
