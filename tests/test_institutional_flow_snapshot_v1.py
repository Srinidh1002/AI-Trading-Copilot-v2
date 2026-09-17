from datetime import date,datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(institutional_flow_snapshot_id="f",created_at=NOW,trading_date=date(2026,1,1),source_id="s",source_timestamp=NOW,publication_state="FINAL",session_reference="END_OF_DAY",currency="INR",cash_flow_unit="CRORE_INR",derivatives_position_unit="CONTRACTS",fii_cash_net=1,dii_cash_net=-1,fii_index_futures_net=None,fii_index_options_net=None,flow_status="READY")
 d.update(x);return InstitutionalFlowSnapshotV1(**d)
def test_final_frozen_and_zero(): 
 assert make(fii_cash_net=0).fii_cash_net==0
 with pytest.raises(FrozenInstanceError):make().fii_cash_net=2
def test_unavailable_and_date_validation():
 assert make(publication_state="UNAVAILABLE",flow_status="UNAVAILABLE",fii_cash_net=None,dii_cash_net=None).flow_status=="UNAVAILABLE"
 with pytest.raises(TypeError):make(trading_date=NOW)
