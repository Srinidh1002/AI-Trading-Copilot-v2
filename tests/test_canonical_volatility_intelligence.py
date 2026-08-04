from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketCandleV1,MarketCandleSeriesV1
from services.technical_intelligence import evaluate_volatility_intelligence
N=datetime(2025,1,1,tzinfo=timezone.utc);P=MarketDataProvenanceV1("T",None,None,"TEST",N,N,False,None,None)
def series(n=40,symbol="NIFTY",exchange="NSE",incomplete=False):
 c=tuple(MarketCandleV1(str(i),symbol,exchange,"5m",N+timedelta(minutes=5*i),N+timedelta(minutes=5*(i+1)),100+i,102+i,99+i,101+i,100+i,not(incomplete and i==n-1),P) for i in range(n));return MarketCandleSeriesV1("s",symbol,exchange,"5m",c,None,None,N)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("n",range(25,41))
def test_volatility_completed_series(symbol,exchange,n):
 r=evaluate_volatility_intelligence(series(n,symbol,exchange));assert r["category"]=="VOLATILITY" and 0<=r["strength"]<=1
@pytest.mark.parametrize("n",range(0,20))
def test_volatility_insufficient_history_blocks(n):
 s=series(n) if n else MarketCandleSeriesV1("s","NIFTY","NSE","5m",(),None,None,N,blockers=("empty",));assert evaluate_volatility_intelligence(s)["bias"]=="UNAVAILABLE"
def test_incomplete_latest_is_excluded():assert evaluate_volatility_intelligence(series(40,incomplete=True))["bias"]==evaluate_volatility_intelligence(series(39))["bias"]
