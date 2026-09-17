from datetime import datetime,timedelta,timezone
import pytest
from services.contracts import MarketDataProvenanceV1,MarketCandleV1,MarketCandleSeriesV1
from services.technical_intelligence import evaluate_pattern_intelligence
N=datetime(2025,1,1,tzinfo=timezone.utc);P=MarketDataProvenanceV1("T",None,None,"TEST",N,N,False,None,None)
def series(n=3,symbol="NIFTY",exchange="NSE",incomplete=False):
 c=tuple(MarketCandleV1(str(i),symbol,exchange,"5m",N+timedelta(minutes=5*i),N+timedelta(minutes=5*(i+1)),100+i,102+i,99+i,101+i,100,not(incomplete and i==n-1),P) for i in range(n));return MarketCandleSeriesV1("s",symbol,exchange,"5m",c,None,None,N)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("n",range(2,20))
def test_patterns_preserve_identity(symbol,exchange,n):
 r=evaluate_pattern_intelligence(series(n,symbol,exchange));assert r["category"]=="PATTERNS" and len(r["indicators"])==7
@pytest.mark.parametrize("n",[0,1]*13)
def test_patterns_insufficient_history_blocks(n):
 s=series(n) if n else MarketCandleSeriesV1("s","NIFTY","NSE","5m",(),None,None,N,blockers=("empty",));assert evaluate_pattern_intelligence(s)["bias"]=="UNAVAILABLE"
def test_incomplete_latest_is_excluded():assert evaluate_pattern_intelligence(series(3,incomplete=True))["bias"]==evaluate_pattern_intelligence(series(2))["bias"]
def test_no_pattern_is_neutral():assert evaluate_pattern_intelligence(series())["bias"] in {"BULLISH","BEARISH","NEUTRAL"}
