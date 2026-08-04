from dataclasses import FrozenInstanceError
import math
import pytest
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY,MarketRegimePolicyV1

def test_defaults_and_derived_weights_are_canonical_and_immutable():
    policy=DEFAULT_MARKET_REGIME_POLICY
    assert policy.required_components==("TECHNICAL","MARKET_SESSION")
    assert policy.optional_components==("BROADER_MARKET","EXTERNAL_CONTEXT")
    assert dict(policy.component_weights)=={"TECHNICAL":.60,"BROADER_MARKET":.25,"EXTERNAL_CONTEXT":.15}
    with pytest.raises(FrozenInstanceError):policy.technical_weight=.1
    with pytest.raises(TypeError):policy.component_weights["TECHNICAL"]=.1

def test_ownership_order_normalizes_and_invalid_ownership_rejects():
    policy=MarketRegimePolicyV1(required_components=("MARKET_SESSION","TECHNICAL"),optional_components=("EXTERNAL_CONTEXT","BROADER_MARKET"))
    assert policy.required_components==("TECHNICAL","MARKET_SESSION")
    assert policy.optional_components==("BROADER_MARKET","EXTERNAL_CONTEXT")
    for changes in ({"required_components":("UNKNOWN","MARKET_SESSION"),"optional_components":("BROADER_MARKET","EXTERNAL_CONTEXT")},{"required_components":("TECHNICAL","TECHNICAL"),"optional_components":("BROADER_MARKET","EXTERNAL_CONTEXT")},{"required_components":["TECHNICAL","MARKET_SESSION"]}):
        with pytest.raises((ValueError,TypeError)):MarketRegimePolicyV1(**changes)

@pytest.mark.parametrize("field",("technical_weight","broader_market_weight","external_context_weight"))
def test_weight_validation_and_non_unit_sum(field):
    assert getattr(MarketRegimePolicyV1(technical_weight=2,broader_market_weight=1,external_context_weight=1),field)==({"technical_weight":2.,"broader_market_weight":1.,"external_context_weight":1.}[field])
    for value in (-.1,True,float("nan"),float("inf"),float("-inf")):
        with pytest.raises(ValueError):MarketRegimePolicyV1(**{field:value})
    with pytest.raises(ValueError):MarketRegimePolicyV1(technical_weight=0,broader_market_weight=0,external_context_weight=0)
