from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1
NOW=datetime(2026,8,3,10,tzinfo=ZoneInfo("Asia/Kolkata"))
def make(action="CALL",**kw):
 v=dict(action_id="action",underlying_symbol="NIFTY",exchange="NSE",cycle_id="cycle",observation_id="observation",candidate_id="candidate",action=action,candidate_direction="BULLISH",candidate_eligibility="ELIGIBLE",confidence=80.,score=80.,regime_suitability="SUITABLE",selected_for_parent_comparison=True,source_ledger_id=None,evaluated_at=NOW,reasons=("ELIGIBLE_BULLISH_CANDIDATE",))
 v.update(kw);return PreEntryMarketActionV1(**v)
def test_call_contract_and_determinism():
 assert make().to_json()==make().to_json()
 with pytest.raises(ValueError):make(action="CALL",candidate_direction="BEARISH")
def test_wait_and_unavailable_invariants():
 assert make(action="WAIT",candidate_direction="NEUTRAL",candidate_eligibility="INELIGIBLE",confidence=0.,score=0.,selected_for_parent_comparison=False,reasons=("DIRECTION_NEUTRAL_NO_ENTRY",)).action=="WAIT"
 assert make(action="UNAVAILABLE",candidate_direction="UNAVAILABLE",candidate_eligibility="UNAVAILABLE",confidence=0.,score=0.,selected_for_parent_comparison=False,blockers=("REQUIRED_EVIDENCE_UNAVAILABLE",),reasons=("REQUIRED_EVIDENCE_UNAVAILABLE",)).action=="UNAVAILABLE"
