from datetime import datetime,timezone
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
def test_input_bundle_is_frozen_and_canonical():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert MarketRegimeInputV1("i",t,"NIFTY","NSE").underlying_symbol=="NIFTY"
