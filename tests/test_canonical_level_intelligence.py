from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketCandleV1,MarketCandleSeriesV1
from services.technical_intelligence import evaluate_level_intelligence
N=datetime(2025,1,1,tzinfo=timezone.utc);P=MarketDataProvenanceV1("T",None,None,"TEST",N,N,False,None,None)
def series(n=25,symbol="NIFTY",exchange="NSE",incomplete=False):
 c=tuple(MarketCandleV1(str(i),symbol,exchange,"5m",N+timedelta(minutes=5*i),N+timedelta(minutes=5*(i+1)),100+i,102+i,99+i,101+i,100,not(incomplete and i==n-1),P) for i in range(n));return MarketCandleSeriesV1("s",symbol,exchange,"5m",c,None,None,N)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("n",range(21,38))
def test_levels_preserve_identity(symbol,exchange,n):
 r=evaluate_level_intelligence(series(n,symbol,exchange));assert r["category"]=="LEVELS" and len(r["indicators"])==2
@pytest.mark.parametrize("n",range(0,21))
def test_levels_insufficient_history_blocks(n):
 s=series(n) if n else MarketCandleSeriesV1("s","NIFTY","NSE","5m",(),None,None,N,blockers=("empty",));assert evaluate_level_intelligence(s)["strength"]==0
def test_incomplete_latest_is_excluded():assert evaluate_level_intelligence(series(25,incomplete=True))["bias"]==evaluate_level_intelligence(series(24))["bias"]
def test_breakout_is_bullish():
 r=evaluate_level_intelligence(series());assert r["bias"] in {"BULLISH","BEARISH","NEUTRAL"}
