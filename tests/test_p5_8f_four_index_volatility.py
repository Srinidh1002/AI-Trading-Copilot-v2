import pytest
from tests.test_volatility_snapshot_v1 import make,NOW
from services.broader_market_intelligence import evaluate_volatility_context
@pytest.mark.parametrize(("symbol","exchange"),(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_four_identities(symbol,exchange):
 assert evaluate_volatility_context(volatility_snapshot=make(underlying_symbol=symbol,exchange=exchange),created_at=NOW,context_id="c").underlying_symbol==symbol
