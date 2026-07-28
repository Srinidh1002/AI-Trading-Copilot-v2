from services.contracts import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY, BroaderMarketIntelligencePolicyV1
def test_default_policy_and_lazy_exports():
 policy=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY
 assert isinstance(policy,BroaderMarketIntelligencePolicyV1)
 assert policy.require_cross_market_evidence is True
 assert policy.require_breadth_evidence is False
 assert policy.require_volatility_context is False
 assert policy.minimum_available_component_count==1
 assert policy.block_on_stale_mandatory_evidence is True
 assert policy.block_on_future_mandatory_evidence is True
 assert policy.block_on_misaligned_mandatory_evidence is True
 assert tuple(policy.required_cross_market_relationships)==(("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("NIFTY","NSE"),("SENSEX","BSE"))
def test_default_has_all_canonical_relationships():
 pairs={(p,r) for p,related in DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY.required_cross_market_relationships.items() for r in related}
 assert pairs=={(("NIFTY","NSE"),("SENSEX","BSE")),(("SENSEX","BSE"),("NIFTY","NSE")),(("BANKNIFTY","NSE"),("FINNIFTY","NSE")),(("FINNIFTY","NSE"),("BANKNIFTY","NSE"))}
