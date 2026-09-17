from datetime import datetime,timedelta,timezone
from services.contracts import MarketDataProvenanceV1,MarketCandleV1,MarketCandleSeriesV1
BASE_TIME=datetime(2025,1,1,12,tzinfo=timezone.utc);CANONICAL_IDENTITIES=(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE"));REQUIRED_TIMEFRAMES=("5m","15m","1h","1d");_MIN={"5m":5,"15m":15,"1h":60,"1d":1440}
def _series(kind="flat",symbol="NIFTY",exchange="NSE",timeframe="5m",series_id=None,candle_count=60,final_incomplete=False,volume=100.):
 step=_MIN[timeframe];p=MarketDataProvenanceV1("FIXTURE",None,None,"TEST",BASE_TIME,BASE_TIME,False,None,None);rows=[]
 for i in range(candle_count):
  delta=(i if kind in {"bullish","breakout","bullish_pattern"} else -i if kind in {"bearish","breakdown","bearish_pattern"} else 0);o=100.+delta;c=o+(1 if kind in {"bullish","breakout"} else -1 if kind in {"bearish","breakdown"} else 0);start=BASE_TIME-timedelta(minutes=step*(candle_count-i));rows.append(MarketCandleV1(f"{series_id or kind}-{i}",symbol,exchange,timeframe,start,start+timedelta(minutes=step),o,max(o,c)+1,min(o,c)-1,c,volume,not(final_incomplete and i==candle_count-1),p))
 return MarketCandleSeriesV1(series_id or f"{symbol}-{timeframe}-{kind}",symbol,exchange,timeframe,tuple(rows),None,None,BASE_TIME,blockers=("empty",) if not rows else ())
def bullish_series(**k):return _series("bullish",**k)
def bearish_series(**k):return _series("bearish",**k)
def flat_series(**k):return _series("flat",**k)
def volatile_expanding_series(**k):return _series("flat",**k)
def volatile_contracting_series(**k):return _series("flat",**k)
def breakout_series(**k):return _series("breakout",**k)
def breakdown_series(**k):return _series("breakdown",**k)
def near_support_series(**k):return _series("flat",**k)
def near_resistance_series(**k):return _series("flat",**k)
def bullish_pattern_series(**k):return _series("bullish_pattern",**k)
def bearish_pattern_series(**k):return _series("bearish_pattern",**k)
def no_pattern_series(**k):return _series("flat",**k)
def insufficient_history_series(**k):return _series(candle_count=5,**k)
def incomplete_series(**k):return _series(final_incomplete=True,**k)
def zero_volume_series(**k):return _series(volume=0.,**k)
