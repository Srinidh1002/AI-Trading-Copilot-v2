"""Fixed UTC fixtures for deterministic P5-9 external-context replay."""
from datetime import date,datetime,timedelta,timezone
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.contracts.external_context_policy_v1 import ExternalContextPolicyV1
from services.external_context import evaluate_external_context_pipeline
EVALUATED_AT=datetime(2026,1,5,9,tzinfo=timezone.utc)
def external_observation(name="GIFT_NIFTY",direction="POSITIVE",change_percent=1.0,**x):
 typ,region,asset=("PREMARKET_INDICATOR","INDIA","EQUITY_INDEX_FUTURE") if name=="GIFT_NIFTY" else (("COMMODITY","GLOBAL","COMMODITY") if name in {"BRENT_CRUDE","WTI_CRUDE"} else ("INDEX_CLOSE","UNITED_STATES","EQUITY_INDEX"))
 d=dict(external_market_observation_id=f"OBS-{name}",created_at=EVALUATED_AT,canonical_name=name,observation_type=typ,market_region=region,asset_class=asset,source_id="REPLAY",source_timestamp=EVALUATED_AT,session_reference="PREMARKET" if name=="GIFT_NIFTY" else "PREVIOUS_SESSION_CLOSE",current_value=101.,previous_value=100.,change_value=1.,change_percent=change_percent,direction=direction,observation_status="READY");d.update(x);return ExternalMarketObservationV1(**d)
def institutional_snapshot(sign=1,**x):
 d=dict(institutional_flow_snapshot_id="FLOW",created_at=EVALUATED_AT,trading_date=date(2026,1,2),source_id="REPLAY_FLOW",source_timestamp=EVALUATED_AT,publication_state="FINAL",session_reference="PREVIOUS_SESSION",currency="INR",cash_flow_unit="CRORE_INR",derivatives_position_unit="CONTRACTS",fii_cash_net=200*sign,dii_cash_net=200*sign,fii_index_futures_net=1000*sign,fii_index_options_net=1000*sign,flow_status="READY");d.update(x);return InstitutionalFlowSnapshotV1(**d)
def scheduled_event(category="RBI_POLICY",**x):
 d=dict(scheduled_market_event_id="EVENT",created_at=EVALUATED_AT,event_name="RBI Policy",event_category=category,scheduled_start=EVALUATED_AT,scheduled_end=None,source_id="REPLAY_EVENT",source_timestamp=EVALUATED_AT,confirmation_state="CONFIRMED",event_status="ACTIVE",severity="HIGH",affected_market_identities=(),affected_exchanges=(),analysis_allowed=True,new_entries_allowed=True,session_override_state="NONE");d.update(x);return ScheduledMarketEventV1(**d)
def external_context_policy(**x):return ExternalContextPolicyV1(**x)
def replay_inputs(symbol="NIFTY",exchange="NSE",observations=(),snapshot=None,events=(),policy=None):return dict(underlying_symbol=symbol,exchange=exchange,observations=observations,institutional_snapshot=snapshot,scheduled_events=events,policy=policy or external_context_policy(),created_at=EVALUATED_AT,global_result_id="GLOBAL",institutional_result_id="INSTITUTIONAL",event_result_id="EVENT",aggregate_result_id="AGGREGATE")
def run_external_context_replay(**x):return evaluate_external_context_pipeline(**replay_inputs(**x))
