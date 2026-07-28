import pytest

from services.contracts.external_context_policy_v1 import ExternalContextPolicyV1


@pytest.mark.parametrize(
    "identity",
    (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")),
)
def test_each_canonical_identity_supports_deterministic_optional_mapping(identity):
    policy = ExternalContextPolicyV1(
        required_observation_names={},
        optional_observation_names={identity: ("DXY", "SP500")},
        minimum_available_global_observations=0,
        minimum_global_confirmation_count=0,
    )
    assert policy.optional_observation_names[identity] == ("DXY", "SP500")


def test_only_canonical_identity_mappings_are_accepted():
    with pytest.raises(ValueError):
        ExternalContextPolicyV1(
            required_observation_names={},
            optional_observation_names={("MIDCPNIFTY", "NSE"): ("SP500",)},
            minimum_available_global_observations=0,
            minimum_global_confirmation_count=0,
        )
