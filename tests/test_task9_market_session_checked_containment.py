from datetime import datetime,time
import pytest
from zoneinfo import ZoneInfo
from services.contracts.task9_market_session_policy_v1 import build_task9_market_session_policy
from services.certification.task9_market_session_evaluator import evaluate_task9_market_session
def test_task8_readiness_boolean_cannot_override_canonical_task9_state():
 p=build_task9_market_session_policy(policy_id="p",policy_version="1",calendar_authority_ref="c",nfo_new_entry_cutoff=time(15,30),bfo_new_entry_cutoff=time(15,30));tz=ZoneInfo("Asia/Kolkata")
 for clock,phase,entries,monitor in [((9,14),"PRE_OPEN",False,False),((15,30),"ENTRY_RESTRICTED",False,True),((15,40),"CLOSED",False,False)]:
  v=datetime(2026,8,17,*clock,tzinfo=tz);s=evaluate_task9_market_session(policy=p,evaluated_at=v,market_date=v.date(),calendar_state="TRADING_DAY");nfo=next(x for x in s.states if x.segment.value=="NFO_OPTIONS");assert (nfo.phase.value,nfo.new_entries_allowed,nfo.position_monitoring_allowed)==(phase,entries,monitor)
def test_readiness_boolean_cannot_supply_missing_canonical_authority():
 with pytest.raises(ValueError):evaluate_task9_market_session(policy=None,evaluated_at=datetime(2026,8,17,10,tzinfo=ZoneInfo("Asia/Kolkata")),market_date=datetime(2026,8,17).date(),calendar_state="TRADING_DAY")
