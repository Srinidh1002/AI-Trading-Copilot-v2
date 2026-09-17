from dataclasses import FrozenInstanceError, replace
from math import inf, nan
import pytest
from services.contracts.broader_market_intelligence_policy_v1 import BroaderMarketIntelligencePolicyV1
def make(**x):
 d=dict(policy_name="policy",required_cross_market_relationships={("NIFTY","NSE"):(("SENSEX","BSE"),),("SENSEX","BSE"):(("NIFTY","NSE"),),("BANKNIFTY","NSE"):(("FINNIFTY","NSE"),),("FINNIFTY","NSE"):(("BANKNIFTY","NSE"),)})
 d.update(x);return BroaderMarketIntelligencePolicyV1(**d)
def test_valid_policy_is_frozen_and_deterministic():
 value=make();assert value.to_json()==value.to_json();assert value.semantic_dict()==value.to_dict()
 with pytest.raises(FrozenInstanceError):value.cross_market_weight=.2
def test_relationships_are_normalized_and_immutable():
 value=make(required_cross_market_relationships={("nifty","nse"):(("sensex","bse"),)})
 assert tuple(value.required_cross_market_relationships)==(("NIFTY","NSE"),)
 with pytest.raises(TypeError):value.required_cross_market_relationships[("NIFTY","NSE")]=()
@pytest.mark.parametrize("field,value",(("minimum_correlation_sample_size",0),("minimum_correlation_lookback",0),("cross_market_weight",nan),("breadth_weight",inf),("minimum_breadth_coverage_ratio",1.1),("bearish_advance_decline_ratio",-1),("maximum_cross_market_age_seconds",-1)))
def test_invalid_numeric_values_rejected(field,value):
 with pytest.raises((TypeError,ValueError)):make(**{field:value})
def test_correlation_and_divergence_ordering_rejected():
 with pytest.raises(ValueError):make(moderate_positive_correlation_threshold=.8)
 with pytest.raises(ValueError):make(divergence_warning_strength=.9,divergence_block_strength=.8)
 with pytest.raises(ValueError):make(minimum_correlation_lookback=29)
def test_breadth_ratio_and_weight_rules_rejected():
 with pytest.raises(ValueError):make(bearish_advance_decline_ratio=1.1)
 with pytest.raises(ValueError):make(cross_market_weight=.5,breadth_weight=.2,volatility_weight=.2)
def test_execution_and_relationship_safety():
 with pytest.raises(ValueError):make(execution_mode="LIVE")
 with pytest.raises(ValueError):make(required_cross_market_relationships={("NIFTY","NSE"):(("BANKNIFTY","NSE"),)})
 with pytest.raises(ValueError):make(required_cross_market_relationships={("NIFTY","NSE"):(("NIFTY","NSE"),)})
