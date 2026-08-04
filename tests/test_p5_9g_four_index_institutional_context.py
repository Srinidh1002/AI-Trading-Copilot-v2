import pytest
from tests.test_institutional_flow_context_evaluator import T,s
from services.external_context import evaluate_institutional_flow_context
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_general_snapshot_applies_to_all(symbol,exchange):assert evaluate_institutional_flow_context(underlying_symbol=symbol,exchange=exchange,snapshot=s(),created_at=T,result_id=symbol)
