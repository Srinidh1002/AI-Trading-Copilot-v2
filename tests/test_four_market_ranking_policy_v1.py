import json,pytest
from services.contracts.four_market_ranking_policy_v1 import DEFAULT_FOUR_MARKET_RANKING_POLICY,FourMarketRankingPolicyV1
def test_defaults_and_serialization_are_deterministic():
 p=DEFAULT_FOUR_MARKET_RANKING_POLICY
 assert p.required_market_identities==(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE"))
 assert list(p.ranking_weights)==["OPPORTUNITY_CONFIDENCE","REGIME_SUITABILITY","TECHNICAL_CONFIRMATION","OPTION_CHAIN_CONFIRMATION","BROADER_MARKET_CONFIRMATION","EXTERNAL_CONTEXT_CONFIRMATION","DATA_QUALITY","LIQUIDITY","EXECUTION_QUALITY"]
 assert json.loads(p.to_json())["tie_tolerance"]==1e-12
 with pytest.raises(TypeError):p.ranking_weights["X"]=1
@pytest.mark.parametrize("value",(-1,True,None,"x",float("nan"),float("inf")))
def test_weight_validation(value):
 with pytest.raises(ValueError):FourMarketRankingPolicyV1(opportunity_confidence_weight=value)
def test_non_unit_weights_supported_and_all_zero_rejected():
 assert FourMarketRankingPolicyV1(opportunity_confidence_weight=2).opportunity_confidence_weight==2.
 with pytest.raises(ValueError):FourMarketRankingPolicyV1(**{n:0 for n in ("opportunity_confidence_weight","regime_suitability_weight","technical_confirmation_weight","option_chain_confirmation_weight","broader_market_confirmation_weight","external_context_confirmation_weight","data_quality_weight","liquidity_weight","execution_quality_weight")})
