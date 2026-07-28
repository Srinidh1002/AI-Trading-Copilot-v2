"""Deterministic completed-candle pattern evidence, with fixed precedence."""
from __future__ import annotations
def evaluate_pattern_intelligence(series, policy=None) -> dict[str,object]:
 from services.contracts import MarketCandleSeriesV1, TechnicalIndicatorValueV1
 from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if policy is None: policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(series,MarketCandleSeriesV1):raise ValueError("A canonical candle series is required.")
 c=tuple(x for x in series.candles if x.is_complete);n=len(c)
 if n<2:
  values=tuple(TechnicalIndicatorValueV1(name,series.timeframe,None,"NONE","INSUFFICIENT_HISTORY",2,n,blockers=("insufficient_complete_candles",)) for name in ("BULLISH_ENGULFING","BEARISH_ENGULFING","HAMMER","SHOOTING_STAR","DOJI","INSIDE_BAR","OUTSIDE_BAR"));return {"category":"PATTERNS","bias":"UNAVAILABLE","strength":0.,"indicators":values,"blockers":("insufficient_complete_candles",),"warnings":()}
 p,x=c[-2],c[-1];body=abs(x.close_price-x.open_price);span=x.high_price-x.low_price;lower=min(x.open_price,x.close_price)-x.low_price;upper=x.high_price-max(x.open_price,x.close_price)
 found="BULLISH_ENGULFING" if p.close_price<p.open_price and x.close_price>x.open_price and x.open_price<=p.close_price and x.close_price>=p.open_price else "BEARISH_ENGULFING" if p.close_price>p.open_price and x.close_price<x.open_price and x.open_price>=p.close_price and x.close_price<=p.open_price else "HAMMER" if span>0 and lower>=body*2 and upper<=max(body,.000000001) else "SHOOTING_STAR" if span>0 and upper>=body*2 and lower<=max(body,.000000001) else "DOJI" if span>0 and body/span<=.1 else "INSIDE_BAR" if x.high_price<p.high_price and x.low_price>p.low_price else "OUTSIDE_BAR" if x.high_price>p.high_price and x.low_price<p.low_price else None
 names=("BULLISH_ENGULFING","BEARISH_ENGULFING","HAMMER","SHOOTING_STAR","DOJI","INSIDE_BAR","OUTSIDE_BAR");values=tuple(TechnicalIndicatorValueV1(name,series.timeframe,1. if name==found else 0.,"BULLISH" if name==found and name in {"BULLISH_ENGULFING","HAMMER"} else "BEARISH" if name==found and name in {"BEARISH_ENGULFING","SHOOTING_STAR"} else "NEUTRAL","VALID",2,n) for name in names);bias="BULLISH" if found in {"BULLISH_ENGULFING","HAMMER"} else "BEARISH" if found in {"BEARISH_ENGULFING","SHOOTING_STAR"} else "NEUTRAL"
 return {"category":"PATTERNS","bias":bias,"strength":1. if bias!="NEUTRAL" else 0.,"indicators":values,"blockers":(),"warnings":()}
