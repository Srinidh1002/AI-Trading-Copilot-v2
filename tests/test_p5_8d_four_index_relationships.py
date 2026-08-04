from datetime import datetime,timedelta,timezone
from services.contracts.market_candle_v1 import MarketCandleV1
from services.contracts.market_candle_series_v1 import MarketCandleSeriesV1
from services.contracts.market_data_provenance_v1 import MarketDataProvenanceV1
from services.broader_market_intelligence import evaluate_cross_market_correlation
import pytest
NOW=datetime(2026,1,1,12,tzinfo=timezone.utc)
def series(symbol,exchange):
 candles=[]
 for i in range(31):
  start=NOW-timedelta(minutes=(31-i)*5);value=100+i
  provenance=MarketDataProvenanceV1("TEST",symbol,exchange,"TEST",start,start,False,None,None)
  candles.append(MarketCandleV1(f"{symbol}-{i}",symbol,exchange,"5m",start,start+timedelta(minutes=5),value,value,value,value,1,True,provenance))
 return MarketCandleSeriesV1(f"{symbol}-series",symbol,exchange,"5m",tuple(candles),None,None,NOW)
@pytest.mark.parametrize(("symbol","exchange","related","related_exchange"),(("NIFTY","NSE","SENSEX","BSE"),("SENSEX","BSE","NIFTY","NSE"),("BANKNIFTY","NSE","FINNIFTY","NSE"),("FINNIFTY","NSE","BANKNIFTY","NSE")))
def test_four_canonical_relationships(symbol,exchange,related,related_exchange):
 result=evaluate_cross_market_correlation(primary_series=series(symbol,exchange),related_series=series(related,related_exchange),created_at=NOW,evidence_id="pair")
 assert (result.primary_symbol,result.related_symbol)==(symbol,related)
