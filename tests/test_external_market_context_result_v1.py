from datetime import datetime,timezone
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
def test_empty_context_is_unavailable():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert ExternalMarketContextResultV1("r",t,"NIFTY","NSE",None,None,None,"UNAVAILABLE","UNAVAILABLE",0,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",True,True,0,3,0,0).to_json()
