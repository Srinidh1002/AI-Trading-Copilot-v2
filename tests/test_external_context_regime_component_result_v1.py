from datetime import datetime,timezone
from services.contracts.external_context_regime_component_result_v1 import ExternalContextRegimeComponentResultV1
def test_unavailable_component():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert ExternalContextRegimeComponentResultV1("r",t,"NIFTY","NSE",None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,0,"UNAVAILABLE")
