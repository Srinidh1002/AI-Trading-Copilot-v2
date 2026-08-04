from datetime import datetime,timezone
from services.contracts import CapitalQuantityTradingCostEvidenceV1
def test_evidence():
 e=CapitalQuantityTradingCostEvidenceV1('e','i','t','p','s',1,25,25,100,1,1,2,0,0,0,0,0,0,3,103,None,None,datetime(2026,1,1,tzinfo=timezone.utc),'CALLER');assert e.to_json()==e.to_json()
