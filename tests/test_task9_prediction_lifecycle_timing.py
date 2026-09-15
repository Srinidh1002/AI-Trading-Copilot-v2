from datetime import datetime,time,timedelta
import pytest
from zoneinfo import ZoneInfo
from services.certification.task9_prediction_lifecycle_timing import resolve_prediction_lifecycle_window
from services.contracts.task9_market_session_state_v1 import Task9SegmentSessionStateV1
from services.market_session.policies import MarketSessionPolicy
from tests.test_task916_prediction_lifecycle_timing_policy import prediction
IST=ZoneInfo("Asia/Kolkata")
def state(segment,day):return Task9SegmentSessionStateV1(segment,day,datetime.combine(day,time(15,31),IST),"Asia/Kolkata","ENTRY_RESTRICTED",True,False,True,False,time(9,15),time(15,30),time(15,40),time(15,40),"TRADING_DAY","p","1")
def test_canonical_bfo_overrides_legacy_and_caps_at_1540():
 v=datetime(2026,8,10,15,31,tzinfo=IST);w=resolve_prediction_lifecycle_window(prediction_record=prediction("WAIT",v,market="SENSEX",exchange="BSE"),session_policy=MarketSessionPolicy(),task9_session_state=state("BFO_OPTIONS",v.date()),task9_segment="BFO_OPTIONS")
 assert w.validity_window_ends_at==datetime(2026,8,10,15,40,tzinfo=IST)
def test_wrong_date_and_segment_canonical_state_fail_closed():
 v=datetime(2026,8,10,15,31,tzinfo=IST);record=prediction("WAIT",v,market="SENSEX",exchange="BSE")
 with pytest.raises(ValueError):resolve_prediction_lifecycle_window(prediction_record=record,session_policy=MarketSessionPolicy(),task9_session_state=state("BFO_OPTIONS",v.date()+timedelta(days=1)),task9_segment="BFO_OPTIONS")
 with pytest.raises(ValueError):resolve_prediction_lifecycle_window(prediction_record=record,session_policy=MarketSessionPolicy(),task9_session_state=state("NFO_OPTIONS",v.date()),task9_segment="BFO_OPTIONS")
