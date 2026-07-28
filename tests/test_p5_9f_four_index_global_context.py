import pytest
from tests.test_global_market_context_evaluator import NOW, observation
from services.external_context import evaluate_global_market_context
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_general_observation_applies_to_all_four(symbol,exchange):
 assert evaluate_global_market_context(underlying_symbol=symbol,exchange=exchange,observations=(observation(),),created_at=NOW,result_id=symbol)
def test_targeted_observation_rejects_other_identity():
 o=observation(affected_market_identities=(("NIFTY","NSE"),))
 with pytest.raises(ValueError):evaluate_global_market_context(underlying_symbol="SENSEX",exchange="BSE",observations=(o,),created_at=NOW,result_id="r")
