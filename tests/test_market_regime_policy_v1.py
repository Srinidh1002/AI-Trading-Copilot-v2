from dataclasses import FrozenInstanceError
import pytest
from services.contracts.market_regime_policy_v1 import MarketRegimePolicyV1
def test_explicit_policy_is_frozen_and_json_safe():
 p=MarketRegimePolicyV1(metadata={"fixture":"policy"})
 with pytest.raises(FrozenInstanceError):p.technical_weight=.1
 assert p.to_dict()==p.to_dict() and p.to_json()==p.to_json()
def test_mapping_weight_threshold_validation():
 with pytest.raises(ValueError):MarketRegimePolicyV1(required_components_by_identity={("NIFTY","BSE"):("TECHNICAL",)})
 policy=MarketRegimePolicyV1(technical_weight=.5,broader_market_weight=.25,external_context_weight=.15)
 assert (policy.technical_weight,policy.broader_market_weight,policy.external_context_weight)==(.5,.25,.15)
 with pytest.raises(ValueError):MarketRegimePolicyV1(range_bound_strength_max=.4,directional_strength_min=.4)
