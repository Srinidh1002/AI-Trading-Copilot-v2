from datetime import datetime,timezone,date
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.external_context import evaluate_institutional_flow_context
T=datetime(2026,1,1,tzinfo=timezone.utc)
def s(**x):
 d=dict(institutional_flow_snapshot_id="s",created_at=T,trading_date=date(2025,12,31),source_id="SRC",source_timestamp=T,publication_state="FINAL",session_reference="PREVIOUS_SESSION",currency="INR",cash_flow_unit="CRORE_INR",derivatives_position_unit="CONTRACTS",fii_cash_net=200,dii_cash_net=200,fii_index_futures_net=1000,fii_index_options_net=1000,flow_status="READY");d.update(x);return InstitutionalFlowSnapshotV1(**d)
def test_aligned_and_conflicting_context():
 assert evaluate_institutional_flow_context(underlying_symbol="NIFTY",exchange="NSE",snapshot=s(),created_at=T,result_id="r").aggregate_direction=="POSITIVE"
 assert evaluate_institutional_flow_context(underlying_symbol="NIFTY",exchange="NSE",snapshot=s(dii_cash_net=-200),created_at=T,result_id="r").context_status=="CONFLICTING"
