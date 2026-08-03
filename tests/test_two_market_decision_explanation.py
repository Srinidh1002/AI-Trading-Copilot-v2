from datetime import datetime
from zoneinfo import ZoneInfo
from services.contracts.market_decision_explanation_v1 import TwoMarketDecisionExplanationV1
NOW=datetime(2026,8,3,10,tzinfo=ZoneInfo("Asia/Kolkata"))
def test_typed_parent_selected_and_no_trade_contracts_are_deterministic():
 selected=TwoMarketDecisionExplanationV1("parent","cycle","decision","SELECTED","CALL","NIFTY","CALL","candidate","NIFTY","SENSEX",("SELECTED_NIFTY_CALL",),("LOWER_RANK",),("WINNER_SCORE=80",),(),(),"nifty","sensex","VALID",(),(),NOW)
 assert selected.to_json()==selected.to_json()
 none=TwoMarketDecisionExplanationV1("parent-none","cycle","decision","NO_TRADE","NO_TRADE","NONE",None,None,None,None,(),(),(),(),("NO_ELIGIBLE_MARKET",),"nifty","sensex","VALID",("NO_ELIGIBLE_MARKET",),(),NOW)
 assert none.selected_market=="NONE"
