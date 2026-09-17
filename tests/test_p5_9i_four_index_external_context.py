import pytest
from datetime import datetime,timezone
from services.external_context import evaluate_external_market_context
@pytest.mark.parametrize("symbol,exchange",(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_all_identities_accept_empty_context(symbol,exchange):assert evaluate_external_market_context(underlying_symbol=symbol,exchange=exchange,global_context=None,institutional_context=None,event_context=None,created_at=datetime(2026,1,1,tzinfo=timezone.utc),result_id=symbol)
