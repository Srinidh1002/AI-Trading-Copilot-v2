from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from services.contracts.task9_market_session_policy_v1 import build_task9_market_session_policy
from services.certification.task9_market_session_evaluator import evaluate_task9_market_session

def test_fno_boundaries_are_segment_aware_and_pure():
 p=build_task9_market_session_policy(policy_id="p",policy_version="1",calendar_authority_ref="c",nfo_new_entry_cutoff=time(15,30),bfo_new_entry_cutoff=time(15,30));tz=ZoneInfo("Asia/Kolkata")
 for value,phase,entry,monitor in [(datetime(2026,8,17,9,14,59,tzinfo=tz),"PRE_OPEN",False,False),(datetime(2026,8,17,9,15,tzinfo=tz),"OPEN",True,True),(datetime(2026,8,17,15,30,tzinfo=tz),"ENTRY_RESTRICTED",False,True),(datetime(2026,8,17,15,40,tzinfo=tz),"CLOSED",False,False)]:
  state=evaluate_task9_market_session(policy=p,evaluated_at=value,market_date=value.date(),calendar_state="TRADING_DAY");nfo=next(x for x in state.states if x.segment.value=="NFO_OPTIONS");assert (nfo.phase.value,nfo.new_entries_allowed,nfo.position_monitoring_allowed)==(phase,entry,monitor)

def test_bfo_and_non_trading_day_fail_closed():
 p=build_task9_market_session_policy(policy_id="p",policy_version="1",calendar_authority_ref="c",nfo_new_entry_cutoff=time(15,30),bfo_new_entry_cutoff=time(15,30));v=datetime(2026,8,17,15,30,tzinfo=ZoneInfo("Asia/Kolkata"));s=evaluate_task9_market_session(policy=p,evaluated_at=v,market_date=v.date(),calendar_state="NON_TRADING_DAY")
 assert all(not x.new_entries_allowed and not x.position_monitoring_allowed for x in s.states)
 with __import__('pytest').raises(ValueError):evaluate_task9_market_session(policy=p,evaluated_at=v,market_date=v.date(),calendar_state="UNKNOWN")
def test_bfo_boundaries_match_nfo_and_missing_authority_fails_closed():
 p=build_task9_market_session_policy(policy_id="p",policy_version="1",calendar_authority_ref="c",nfo_new_entry_cutoff=time(15,30),bfo_new_entry_cutoff=time(15,30));tz=ZoneInfo("Asia/Kolkata")
 for clock,phase in [((9,14,59),"PRE_OPEN"),((9,15,0),"OPEN"),((15,29,59),"OPEN"),((15,30,0),"ENTRY_RESTRICTED"),((15,39,59),"ENTRY_RESTRICTED"),((15,40,0),"CLOSED")]:
  v=datetime(2026,8,17,*clock,tzinfo=tz);bfo=next(x for x in evaluate_task9_market_session(policy=p,evaluated_at=v,market_date=v.date(),calendar_state="TRADING_DAY").states if x.segment.value=="BFO_OPTIONS");assert bfo.phase.value==phase
 import pytest
 with pytest.raises(ValueError):evaluate_task9_market_session(policy=None,evaluated_at=datetime(2026,8,17,10,tzinfo=tz),market_date=date(2026,8,17),calendar_state="TRADING_DAY")
