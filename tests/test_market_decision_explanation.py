from datetime import datetime
from zoneinfo import ZoneInfo
from services.contracts.market_decision_explanation_v1 import MarketEvidenceExplanationEntryV1,MarketDecisionExplanationV1
NOW=datetime(2026,8,3,10,tzinfo=ZoneInfo("Asia/Kolkata"))
def test_explanation_contract_is_deterministic_paper_only():
 e=MarketEvidenceExplanationEntryV1("entry","SUPPORTING","action",None,None,"BULLISH","READY",4,"ELIGIBLE_BULLISH_CANDIDATE",80.,None,NOW,True,False)
 value=MarketDecisionExplanationV1("explanation","NIFTY","NSE","cycle","observation","candidate","action","CALL","ELIGIBLE","BULLISH",80.,80.,"SUITABLE",(e,),action_reason_codes=("ELIGIBLE_BULLISH_CANDIDATE",))
 assert value.to_json()==value.to_json()
