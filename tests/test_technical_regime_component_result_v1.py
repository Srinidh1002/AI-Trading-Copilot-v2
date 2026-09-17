from datetime import datetime,timezone
from services.contracts.technical_regime_component_result_v1 import TechnicalRegimeComponentResultV1
def test_unavailable_component_constructs():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert TechnicalRegimeComponentResultV1("r",t,"NIFTY","NSE",None,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0.,0.,"UNAVAILABLE",0,0)
