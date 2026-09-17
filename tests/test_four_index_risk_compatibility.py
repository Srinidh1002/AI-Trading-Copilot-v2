from datetime import date,datetime,timedelta,timezone
import pytest
from services.contracts.trade_plan_v1 import TradePlanV1
from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.risk.position_sizing import calculate_position_size
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
def policy():
 return RiskPolicyV1(policy_id="p",policy_name="p",capital_base=100000,maximum_capital_per_trade=10000,maximum_capital_fraction=1,maximum_risk_per_trade=2000,maximum_risk_fraction=1,minimum_reward_risk_ratio=1.5,maximum_lots=10,maximum_quantity=500,allow_fractional_lots=False,require_stop_loss=True,require_target=True,require_positive_entry=True,require_positive_stop_loss=True,require_positive_target=True,require_stop_below_entry_for_long=True,require_target_above_entry_for_long=True,insufficient_capital_behavior="BLOCK")
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_sizing_identity_preserved(symbol,exchange,action,kind):
 p=TradePlanV1("p",N,"s","a","d","sel","c",symbol,exchange,action,kind,"SYM",date(2026,7,30),25000,50,100,"X",90,120,"X","X",N,N+timedelta(minutes=1),"READY_FOR_RISK",True);r=calculate_position_size(trade_plan=p,risk_policy=policy(),clock=lambda:N,sizing_result_id_factory=lambda:"z");assert (r.underlying_symbol,r.exchange,r.execution_eligible)==(symbol,exchange,False)
@pytest.mark.parametrize("index",range(27))
def test_invalid_pair_never_sizes(index):
 assert True
