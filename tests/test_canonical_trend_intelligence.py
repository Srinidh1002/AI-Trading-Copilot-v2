from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketCandleV1,MarketCandleSeriesV1
from services.technical_intelligence import evaluate_trend_intelligence
N=datetime(2025,1,1,tzinfo=timezone.utc);P=MarketDataProvenanceV1("T",None,None,"TEST",N,N,False,None,None)
def series(n=80,symbol="NIFTY",exchange="NSE",incomplete=False):
 c=tuple(MarketCandleV1(str(i),symbol,exchange,"5m",N+timedelta(minutes=5*i),N+timedelta(minutes=5*(i+1)),100+i,102+i,99+i,101+i,100,not(incomplete and i==n-1),P) for i in range(n));return MarketCandleSeriesV1("s",symbol,exchange,"5m",c,None,None,N)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("n",range(55,71))
def test_trend_completed_series(symbol,exchange,n):
 r=evaluate_trend_intelligence(series(n,symbol,exchange));assert r["category"]=="TREND" and r["bias"] in {"BULLISH","BEARISH","NEUTRAL","UNAVAILABLE"}
@pytest.mark.parametrize("n",range(0,25))
def test_trend_insufficient_history_blocks(n):
 r=evaluate_trend_intelligence(series(n) if n else MarketCandleSeriesV1("s","NIFTY","NSE","5m",(),None,None,N,blockers=("empty",)));assert r["bias"]=="UNAVAILABLE" and r["strength"]==0
def test_incomplete_latest_is_excluded():assert evaluate_trend_intelligence(series(80,incomplete=True))["bias"]==evaluate_trend_intelligence(series(79))["bias"]
