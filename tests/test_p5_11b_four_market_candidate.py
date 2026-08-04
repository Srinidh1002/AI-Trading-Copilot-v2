import pytest
from tests.test_market_opportunity_candidate_v1 import make_candidate
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES
@pytest.mark.parametrize("identity",IDENTITIES)
def test_equivalent_candidates_are_identity_neutral(identity):
 c=make_candidate(identity)
 assert (c.underlying_symbol,c.exchange)==identity
 assert c.regime_suitability_score==.8 and c.execution_mode=="PAPER"
@pytest.mark.parametrize("identity",(("NIFTY","BSE"),("SENSEX","NSE"),("X","NSE")))
def test_invalid_identity_rejected(identity):
 with pytest.raises(ValueError): make_candidate(identity)
