import pytest
from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1
def test_identity_order_normalizes_and_invalid_identities_reject():
 p=FourMarketRankingPolicyV1(required_market_identities=(("SENSEX","BSE"),("NIFTY","NSE"),("FINNIFTY","NSE"),("BANKNIFTY","NSE")))
 assert p.required_market_identities[0]==("NIFTY","NSE")
 with pytest.raises(ValueError):FourMarketRankingPolicyV1(required_market_identities=(("NIFTY","NSE"),)*4)
@pytest.mark.parametrize("field",("block_candidate_when_analysis_disallowed","allow_conflicting_candidate_to_rank","rank_only_eligible_candidates"))
def test_flags_require_exact_bool(field):
 with pytest.raises(ValueError):FourMarketRankingPolicyV1(**{field:1})
