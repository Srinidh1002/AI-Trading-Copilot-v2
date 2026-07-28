import pytest
from tests.test_broader_market_intelligence_evaluator import NOW,cross
from services.broader_market_intelligence import evaluate_broader_market_intelligence
@pytest.mark.parametrize(("symbol","exchange","related","related_exchange","relationship"),(("NIFTY","NSE","SENSEX","BSE","BROAD_MARKET"),("SENSEX","BSE","NIFTY","NSE","BROAD_MARKET"),("BANKNIFTY","NSE","FINNIFTY","NSE","FINANCIAL_INDEX"),("FINNIFTY","NSE","BANKNIFTY","NSE","FINANCIAL_INDEX")))
def test_four_identities(symbol,exchange,related,related_exchange,relationship):
 item=cross(primary_symbol=symbol,primary_exchange=exchange,related_symbol=related,related_exchange=related_exchange,relationship_type=relationship)
 assert evaluate_broader_market_intelligence(underlying_symbol=symbol,exchange=exchange,cross_market_evidence=(item,),breadth_evidence=None,volatility_context=None,created_at=NOW,result_id="r").underlying_symbol==symbol
