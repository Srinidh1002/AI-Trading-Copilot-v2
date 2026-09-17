"""Completed-candle trend evidence; it never produces a trade decision."""
from __future__ import annotations
from .indicators import calculate_adx, calculate_ema

def _blocked(name, timeframe, minimum, available):
    from services.contracts.technical_indicator_value_v1 import TechnicalIndicatorValueV1
    return TechnicalIndicatorValueV1(name,timeframe,None,"NONE","INSUFFICIENT_HISTORY",minimum,available,blockers=("insufficient_complete_candles",))
def evaluate_trend_intelligence(series, policy=None) -> dict[str, object]:
    from services.contracts import MarketCandleSeriesV1, TechnicalIndicatorValueV1
    from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if policy is None: policy = DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if not isinstance(series, MarketCandleSeriesV1): raise ValueError("A canonical candle series is required.")
    candles=tuple(c for c in series.candles if c.is_complete); closes=tuple(c.close_price for c in candles); highs=tuple(c.high_price for c in candles); lows=tuple(c.low_price for c in candles); n=len(candles)
    fast,slow,adx=calculate_ema(closes,policy.ema_fast_period),calculate_ema(closes,policy.ema_slow_period),calculate_adx(highs,lows,closes,policy.adx_period)
    indicators=(TechnicalIndicatorValueV1("EMA_FAST",series.timeframe,fast,"BULLISH" if fast is not None and closes[-1]>=fast else "BEARISH" if fast is not None else "NONE","VALID",policy.ema_fast_period,n,(("period",policy.ema_fast_period),)) if fast is not None else _blocked("EMA_FAST",series.timeframe,policy.ema_fast_period,n),TechnicalIndicatorValueV1("EMA_SLOW",series.timeframe,slow,"BULLISH" if slow is not None and closes[-1]>=slow else "BEARISH" if slow is not None else "NONE","VALID",policy.ema_slow_period,n,(("period",policy.ema_slow_period),)) if slow is not None else _blocked("EMA_SLOW",series.timeframe,policy.ema_slow_period,n),TechnicalIndicatorValueV1("ADX",series.timeframe,adx,"HIGH" if adx is not None and adx>=policy.adx_threshold else "LOW" if adx is not None else "NONE","VALID",policy.adx_period*2+1,n,(("period",policy.adx_period),)) if adx is not None else _blocked("ADX",series.timeframe,policy.adx_period*2+1,n))
    if fast is None or slow is None or adx is None: return {"category":"TREND","bias":"UNAVAILABLE","strength":0.0,"indicators":indicators,"blockers":("insufficient_complete_candles",),"warnings":()}
    bullish=fast>slow and closes[-1]>fast; bearish=fast<slow and closes[-1]<fast; bias="BULLISH" if bullish else "BEARISH" if bearish else "NEUTRAL"
    return {"category":"TREND","bias":bias,"strength":adx/100.0 if bias!="NEUTRAL" else 0.0,"indicators":indicators,"blockers":(),"warnings":()}
