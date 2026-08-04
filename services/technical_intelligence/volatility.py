"""Completed-candle volatility and volume evidence, without regime output."""
from __future__ import annotations
from .indicators import calculate_atr,calculate_bollinger_bands,calculate_volume_average,calculate_vwap
def _blocked(name,timeframe,minimum,available):
 from services.contracts.technical_indicator_value_v1 import TechnicalIndicatorValueV1
 return TechnicalIndicatorValueV1(name,timeframe,None,"NONE","INSUFFICIENT_HISTORY",minimum,available,blockers=("insufficient_complete_candles",))
def evaluate_volatility_intelligence(series, policy=None) -> dict[str,object]:
 from services.contracts import MarketCandleSeriesV1, TechnicalIndicatorValueV1
 from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if policy is None: policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(series,MarketCandleSeriesV1):raise ValueError("A canonical candle series is required.")
 c=tuple(x for x in series.candles if x.is_complete);n=len(c);h=tuple(x.high_price for x in c);l=tuple(x.low_price for x in c);close=tuple(x.close_price for x in c);v=tuple(x.volume for x in c);atr=calculate_atr(h,l,close,policy.atr_period);bands=calculate_bollinger_bands(close,policy.bollinger_period,policy.bollinger_stddev);average=calculate_volume_average(v,policy.volume_lookback);vwap=calculate_vwap(h,l,close,v)
 values=(TechnicalIndicatorValueV1("ATR",series.timeframe,atr,"HIGH" if atr is not None and atr/close[-1]>=.02 else "LOW" if atr is not None else "NONE","VALID",policy.atr_period,n,(("period",policy.atr_period),)) if atr is not None else _blocked("ATR",series.timeframe,policy.atr_period,n),TechnicalIndicatorValueV1("BOLLINGER_WIDTH",series.timeframe,(bands[2]-bands[0])/bands[1] if bands is not None and bands[1] else None,"EXPANDING" if bands is not None else "NONE","VALID",policy.bollinger_period,n,(("period",policy.bollinger_period),("stddev",policy.bollinger_stddev))) if bands is not None else _blocked("BOLLINGER_WIDTH",series.timeframe,policy.bollinger_period,n),TechnicalIndicatorValueV1("VOLUME_AVERAGE",series.timeframe,average,"HIGH" if average is not None and v[-1]>=average else "LOW" if average is not None else "NONE","VALID",policy.volume_lookback,n,(("period",policy.volume_lookback),)) if average is not None else _blocked("VOLUME_AVERAGE",series.timeframe,policy.volume_lookback,n),TechnicalIndicatorValueV1("VWAP",series.timeframe,vwap,"BULLISH" if vwap is not None and close[-1]>vwap else "BEARISH" if vwap is not None else "NONE","VALID",1,n) if vwap is not None else _blocked("VWAP",series.timeframe,1,n))
 if atr is None or bands is None or average is None or vwap is None:return {"category":"VOLATILITY","bias":"UNAVAILABLE","strength":0.,"indicators":values,"blockers":("insufficient_complete_candles",),"warnings":()}
 width=(bands[2]-bands[0])/bands[1] if bands[1] else 0.;bias="BULLISH" if close[-1]>vwap else "BEARISH" if close[-1]<vwap else "NEUTRAL"
 return {"category":"VOLATILITY","bias":bias,"strength":min(1.,width+atr/close[-1]) if bias!="NEUTRAL" else 0.,"indicators":values,"blockers":(),"warnings":()}
