"""Completed-candle momentum evidence only."""
from __future__ import annotations
from .indicators import calculate_macd, calculate_rsi
def _blocked(name,timeframe,minimum,available):
    from services.contracts.technical_indicator_value_v1 import TechnicalIndicatorValueV1
    return TechnicalIndicatorValueV1(name,timeframe,None,"NONE","INSUFFICIENT_HISTORY",minimum,available,blockers=("insufficient_complete_candles",))
def evaluate_momentum_intelligence(series, policy=None) -> dict[str, object]:
    from services.contracts import MarketCandleSeriesV1, TechnicalIndicatorValueV1
    from services.contracts.technical_intelligence_policy_v1 import DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if policy is None: policy = DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if not isinstance(series,MarketCandleSeriesV1):raise ValueError("A canonical candle series is required.")
    candles=tuple(c for c in series.candles if c.is_complete); closes=tuple(c.close_price for c in candles);n=len(candles); rsi=calculate_rsi(closes,policy.rsi_period);macd=calculate_macd(closes,policy.macd_fast_period,policy.macd_slow_period,policy.macd_signal_period)
    rsi_signal="OVERBOUGHT" if rsi is not None and rsi>=policy.rsi_overbought else "OVERSOLD" if rsi is not None and rsi<=policy.rsi_oversold else "NEUTRAL" if rsi is not None else "NONE"
    values=(TechnicalIndicatorValueV1("RSI",series.timeframe,rsi,rsi_signal,"VALID",policy.rsi_period+1,n,(("period",policy.rsi_period),)) if rsi is not None else _blocked("RSI",series.timeframe,policy.rsi_period+1,n),TechnicalIndicatorValueV1("MACD",series.timeframe,macd[0],"BULLISH" if macd is not None and macd[2]>0 else "BEARISH" if macd is not None else "NONE","VALID",policy.macd_slow_period+policy.macd_signal_period-1,n,(("fast",policy.macd_fast_period),("slow",policy.macd_slow_period),("signal",policy.macd_signal_period))) if macd is not None else _blocked("MACD",series.timeframe,policy.macd_slow_period+policy.macd_signal_period-1,n))
    if rsi is None or macd is None:return {"category":"MOMENTUM","bias":"UNAVAILABLE","strength":0.0,"indicators":values,"blockers":("insufficient_complete_candles",),"warnings":()}
    bullish=macd[2]>0 and rsi<policy.rsi_overbought;bearish=macd[2]<0 and rsi>policy.rsi_oversold; bias="BULLISH" if bullish else "BEARISH" if bearish else "NEUTRAL";strength=min(1.,abs(macd[2])/(abs(closes[-1]) or 1.)*20+abs(rsi-50)/50*.25) if bias!="NEUTRAL" else 0.
    return {"category":"MOMENTUM","bias":bias,"strength":strength,"indicators":values,"blockers":(),"warnings":()}
