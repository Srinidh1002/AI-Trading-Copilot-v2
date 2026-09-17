from datetime import datetime,timedelta,timezone
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.external_context import evaluate_event_risk_context
T=datetime(2026,1,1,tzinfo=timezone.utc)
def event(**x):
 d=dict(scheduled_market_event_id="e",created_at=T,event_name="RBI Policy",event_category="RBI_POLICY",scheduled_start=T+timedelta(minutes=10),scheduled_end=None,source_id="SRC",source_timestamp=T,confirmation_state="CONFIRMED",event_status="UPCOMING",severity="HIGH",affected_market_identities=(),affected_exchanges=(),analysis_allowed=True,new_entries_allowed=True,session_override_state="NONE");d.update(x);return ScheduledMarketEventV1(**d)
def test_rbi_lead_window_blocks_entries():assert evaluate_event_risk_context(underlying_symbol="NIFTY",exchange="NSE",events=(event(),),created_at=T,result_id="r").entry_restriction_state=="BLOCKED"
def test_empty_events_are_unavailable():assert evaluate_event_risk_context(underlying_symbol="NIFTY",exchange="NSE",events=(),created_at=T,result_id="r").context_status=="UNAVAILABLE"
