import pytest
from unittest.mock import Mock
from tests.test_p5_8d_four_index_relationships import NOW,series
from services.broader_market_intelligence import build_broader_market_intelligence
@pytest.mark.parametrize(("symbol","exchange","related","related_exchange"),(("NIFTY","NSE","SENSEX","BSE"),("SENSEX","BSE","NIFTY","NSE"),("BANKNIFTY","NSE","FINNIFTY","NSE"),("FINNIFTY","NSE","BANKNIFTY","NSE")))
def test_four_pairs(symbol,exchange,related,related_exchange):
 aggregate=Mock(return_value="result")
 assert build_broader_market_intelligence(primary_series=series(symbol,exchange),related_series=series(related,related_exchange),created_at=NOW,cross_market_evidence_id="c",result_id="r",correlation_evaluator=Mock(return_value=object()),aggregate_evaluator=aggregate)=="result"
