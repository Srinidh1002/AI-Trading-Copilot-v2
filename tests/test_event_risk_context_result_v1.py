from datetime import datetime,timezone
from services.contracts.event_risk_context_result_v1 import EventRiskContextResultV1
T=datetime(2026,1,1,tzinfo=timezone.utc)
def test_unavailable_empty_result_serializes():
 r=EventRiskContextResultV1("r",T,"NIFTY","NSE",(),"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",True,True,0,0,0,0,0,"UNAVAILABLE");assert r.to_json()
