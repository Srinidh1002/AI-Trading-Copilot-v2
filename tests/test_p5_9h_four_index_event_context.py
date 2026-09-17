import pytest
from tests.test_event_risk_context_evaluator import T,event
from services.external_context import evaluate_event_risk_context
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_general_event_applies_to_all(symbol,exchange):assert evaluate_event_risk_context(underlying_symbol=symbol,exchange=exchange,events=(event(),),created_at=T,result_id=symbol)
