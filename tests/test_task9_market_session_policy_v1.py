from datetime import time
import pytest
from services.contracts.task9_market_session_policy_v1 import *
def test_canonical_policy_round_trips_and_requires_explicit_cutoffs():
 p=build_task9_market_session_policy(policy_id="session",policy_version="1",calendar_authority_ref="calendar.v1",nfo_new_entry_cutoff=time(15,30),bfo_new_entry_cutoff=time(15,30))
 assert Task9MarketSessionPolicyV1.from_dict(p.to_dict())==p
 with pytest.raises(ValueError):build_task9_market_session_policy(policy_id="s",policy_version="1",calendar_authority_ref="c",nfo_new_entry_cutoff=None,bfo_new_entry_cutoff=time(15,30))
def test_fno_window_rejects_legacy_close_and_invalid_cutoff():
 with pytest.raises(ValueError):Task9SegmentSessionWindowV1("NFO_OPTIONS",time(9,15),time(15,30),time(15,20),time(15,30))
 with pytest.raises(ValueError):Task9SegmentSessionWindowV1("BFO_OPTIONS",time(9,15),time(15,40),time(9,15),time(15,40))
@pytest.mark.parametrize("open_time,close,cutoff,monitor",[(time(9,16),time(15,40),time(15,30),time(15,40)),(time(9,15),time(15,40),time(15,41),time(15,40)),(time(9,15),time(15,40),time(15,30),time(15,29))])
def test_fno_canonical_bounds_and_monitoring_are_strict(open_time,close,cutoff,monitor):
 with pytest.raises(ValueError):Task9SegmentSessionWindowV1("NFO_OPTIONS",open_time,close,cutoff,monitor)
