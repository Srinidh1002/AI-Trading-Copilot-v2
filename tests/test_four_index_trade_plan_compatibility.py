from datetime import date,datetime,timedelta,timezone
import pytest
from services.contracts.trade_plan_v1 import TradePlanV1
N=datetime(2026,7,27,10,tzinfo=timezone.utc)
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("BANKNIFTY","NSE","BUY","CALL"),("BANKNIFTY","NSE","SELL","PUT"),("FINNIFTY","NSE","BUY","CALL"),("FINNIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_four_index_risk_pending_plan(symbol,exchange,action,kind):
 p=TradePlanV1("p",N,"s","a","d","sel","c",symbol,exchange,action,kind,"SYM",date(2026,7,30),25000,50,100,"X",90,120,"X","X",N,N+timedelta(minutes=1),"READY_FOR_RISK",True);assert p.execution_eligible is False
@pytest.mark.parametrize("index",range(22))
def test_plan_invalid_pair_rejected(index):
 with pytest.raises(ValueError):TradePlanV1("p",N,"s","a","d","sel","c","FINNIFTY","BSE","BUY","CALL","SYM",date(2026,7,30),25000,50,100,"X",90,120,"X","X",N,N+timedelta(minutes=1),"READY_FOR_RISK",True)
