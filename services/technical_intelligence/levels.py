"""Historical completed-candle support and resistance evidence."""
from __future__ import annotations
def evaluate_level_intelligence(series, policy=None) -> dict[str,object]:
 from services.contracts import MarketCandleSeriesV1, TechnicalIndicatorValueV1
 from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if policy is None: policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(series,MarketCandleSeriesV1):raise ValueError("A canonical candle series is required.")
 c=tuple(x for x in series.candles if x.is_complete);n=len(c);minimum=policy.support_resistance_lookback+1
 if n<minimum:
  values=tuple(TechnicalIndicatorValueV1(name,series.timeframe,None,"NONE","INSUFFICIENT_HISTORY",minimum,n,blockers=("insufficient_complete_candles",)) for name in ("SUPPORT","RESISTANCE"));return {"category":"LEVELS","bias":"UNAVAILABLE","strength":0.,"indicators":values,"blockers":("insufficient_complete_candles",),"warnings":()}
 # The latest completed candle is compared with an earlier historical window.
 prior=c[-minimum:-1];last=c[-1];support=min(x.low_price for x in prior);resistance=max(x.high_price for x in prior);range_=max(resistance-support,1e-12); near_support=(last.close_price-support)/range_<=.1;near_resistance=(resistance-last.close_price)/range_<=.1;breakout=last.close_price>resistance;breakdown=last.close_price<support
 signal="BULLISH" if breakout or near_support else "BEARISH" if breakdown or near_resistance else "NEUTRAL";strength=1. if breakout or breakdown else .5 if signal!="NEUTRAL" else 0.
 values=(TechnicalIndicatorValueV1("SUPPORT",series.timeframe,support,"LOW" if near_support else "NONE","VALID",minimum,n,(("lookback",policy.support_resistance_lookback),)),TechnicalIndicatorValueV1("RESISTANCE",series.timeframe,resistance,"HIGH" if near_resistance else "NONE","VALID",minimum,n,(("lookback",policy.support_resistance_lookback),)))
 return {"category":"LEVELS","bias":signal,"strength":strength,"indicators":values,"blockers":(),"warnings":()}
