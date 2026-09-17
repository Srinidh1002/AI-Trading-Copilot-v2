from datetime import date,datetime,time
import pytest
from zoneinfo import ZoneInfo
from services.contracts.task9_market_session_state_v1 import *
def state(phase="OPEN",**k):
 tz=ZoneInfo("Asia/Kolkata");v=dict(segment="NFO_OPTIONS",market_date=date(2026,8,17),evaluated_at=datetime(2026,8,17,10,tzinfo=tz),timezone="Asia/Kolkata",phase=phase,market_open=True,new_entries_allowed=True,position_monitoring_allowed=True,close_drain_required=False,session_open_time=time(9,15),new_entry_cutoff=time(15,30),position_monitoring_until=time(15,40),session_close_time=time(15,40),calendar_status="TRADING_DAY",policy_id="p",policy_version="1");v.update(k);return Task9SegmentSessionStateV1(**v)
def test_state_roundtrip_and_phase_contradictions_fail_closed():
 s=state();assert Task9SegmentSessionStateV1.from_dict(s.to_dict())==s;assert Task9MarketSessionStateV1.from_dict(Task9MarketSessionStateV1(s.evaluated_at,s.market_date,s.timezone,(s,)).to_dict()).states==(s,)
 for phase in ("PRE_OPEN","CLOSED","NON_TRADING_DAY","ENTRY_RESTRICTED"):
  with pytest.raises(ValueError):state(phase,market_open=True,new_entries_allowed=True,position_monitoring_allowed=True)
def test_state_provenance_and_aggregate_validation():
 with pytest.raises(ValueError):state(policy_id="")
 with pytest.raises(ValueError):state(timezone="UTC")
 with pytest.raises(ValueError):state(evaluated_at=datetime(2026,8,17,10))
 s=state()
 with pytest.raises(ValueError):Task9MarketSessionStateV1(s.evaluated_at,s.market_date,s.timezone,(s,s))
 with pytest.raises(ValueError):Task9MarketSessionStateV1(s.evaluated_at,s.market_date,s.timezone,(state(market_date=date(2026,8,18)),))
