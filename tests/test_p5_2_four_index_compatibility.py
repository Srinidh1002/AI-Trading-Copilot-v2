import pytest
from services.data_quality import evaluate_market_quote_quality
from test_market_quote_v1 import quote,NOW
CASES=(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE"))
@pytest.mark.parametrize("pair",CASES)
@pytest.mark.parametrize("n",range(13))
def test_four_index(pair,n):assert evaluate_market_quote_quality(quote(*pair),clock=lambda:NOW).underlying_symbol==pair[0]
