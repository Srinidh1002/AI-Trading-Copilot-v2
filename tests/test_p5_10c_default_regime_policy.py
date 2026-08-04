from services.contracts import DEFAULT_MARKET_REGIME_POLICY,MarketRegimePolicyV1
def test_default_policy_lazy_exports_and_defaults():
 p=DEFAULT_MARKET_REGIME_POLICY;assert isinstance(p,MarketRegimePolicyV1);assert p.technical_weight>p.broader_market_weight>p.external_context_weight;assert all("TECHNICAL" in v for v in p.required_components_by_identity.values())
