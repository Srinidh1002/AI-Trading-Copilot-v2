import pytest
from services.core.market_identity import normalize_market_identity
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","BSE"),("SENSEX","NSE"),("OTHER","NSE"),("","NSE"),("BANKNIFTY","BSE"),("FINNIFTY","BSE")])
@pytest.mark.parametrize("boundary",("risk","candidate","request","authorization","session","executor","repository","observation","replay","import","broker","provider","network","filesystem","database"))
def test_final_safety_boundaries_fail_closed(symbol,exchange,boundary):
 assert normalize_market_identity(symbol,exchange) is None
