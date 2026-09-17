from datetime import datetime,timezone
from services.contracts.broader_market_regime_component_result_v1 import BroaderMarketRegimeComponentResultV1
def test_unavailable_component():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert BroaderMarketRegimeComponentResultV1("r",t,"NIFTY","NSE",None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,"UNAVAILABLE",0,0)
