from datetime import datetime,timezone,date
import pytest
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.contracts.institutional_flow_context_result_v1 import InstitutionalFlowContextResultV1
T=datetime(2026,1,1,tzinfo=timezone.utc)
def snap():return InstitutionalFlowSnapshotV1("s",T,date(2025,12,31),"SRC",T,"FINAL","PREVIOUS_SESSION","INR","CRORE_INR","CONTRACTS",200,200,1000,1000,"READY")
def test_ready_result():
 s=snap();r=InstitutionalFlowContextResultV1("r",T,"NIFTY","NSE",s,"READY","POSITIVE",.5,"CONFIRMING","FINAL","PREVIOUS_SESSION",4,0,"POSITIVE","POSITIVE","POSITIVE","POSITIVE","POSITIVE","POSITIVE",source_timestamps={"SRC":T});assert r.to_json()
def test_blocked_requires_blocker():
 with pytest.raises(ValueError):InstitutionalFlowContextResultV1("r",T,"NIFTY","NSE",None,"BLOCKED","UNAVAILABLE",0,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE",0,4,"UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","UNAVAILABLE")
