import pytest
from datetime import datetime,timezone
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
@pytest.mark.parametrize("s,e",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_four_market_input(s,e):assert MarketRegimeInputV1(s,datetime(2026,1,1,tzinfo=timezone.utc),s,e).exchange==e
