"""One supplied P5-3 timeframe evidence item to technical evidence."""
from __future__ import annotations
from datetime import datetime,timezone

def _now(clock):
    value=clock() if clock else datetime.now(timezone.utc)
    if not isinstance(value,datetime) or value.tzinfo is None: raise ValueError("Clock must return timezone-aware datetime.")
    return value
def _unique(values): return tuple(dict.fromkeys(values))
def analyze_timeframe_technical_evidence(*,candle_series,timeframe_evidence,policy=None,clock=None,timeframe_technical_evidence_id_factory=None):
    from services.contracts import MarketCandleSeriesV1,TimeframeEvidenceV1,TechnicalIntelligencePolicyV1,TimeframeTechnicalEvidenceV1,DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if not isinstance(candle_series,MarketCandleSeriesV1) or not isinstance(timeframe_evidence,TimeframeEvidenceV1): raise ValueError("Canonical candle series and timeframe evidence are required.")
    if policy is None: policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
    if not isinstance(policy,TechnicalIntelligencePolicyV1) or (clock is not None and not callable(clock)) or (timeframe_technical_evidence_id_factory is not None and not callable(timeframe_technical_evidence_id_factory)):raise ValueError("Invalid technical analysis controls.")
    if (candle_series.series_id,candle_series.underlying_symbol,candle_series.exchange,candle_series.timeframe)!=(timeframe_evidence.candle_series_id,timeframe_evidence.underlying_symbol,timeframe_evidence.exchange,timeframe_evidence.timeframe) or candle_series.timeframe not in policy.required_timeframes:raise ValueError("Series/evidence linkage mismatch.")
    now=_now(clock); identity=(lambda: f"technical-{candle_series.series_id}") if timeframe_technical_evidence_id_factory is None else timeframe_technical_evidence_id_factory; evidence_id=identity()
    if not isinstance(evidence_id,str) or not evidence_id.strip():raise ValueError("Invalid technical evidence id.")
    bad={"STALE","FUTURE","EMPTY","MALFORMED","UNSUPPORTED","FAILED"};blocked=list(timeframe_evidence.blockers)
    if timeframe_evidence.quality_status in bad:blocked.append("timeframe_quality_"+timeframe_evidence.quality_status.lower())
    if timeframe_evidence.latest_candle_complete is False and policy.incomplete_timeframe_behavior=="BLOCK":blocked.append("incomplete_timeframe")
    if not timeframe_evidence.history_sufficient and policy.insufficient_history_behavior=="BLOCK":blocked.append("insufficient_history")
    base=dict(timeframe_technical_evidence_id=evidence_id,created_at=now,underlying_symbol=candle_series.underlying_symbol,exchange=candle_series.exchange,timeframe=candle_series.timeframe,timeframe_evidence_id=timeframe_evidence.timeframe_evidence_id)
    if blocked:return TimeframeTechnicalEvidenceV1(**base,indicators=(),category_biases=(("TREND","UNAVAILABLE"),("MOMENTUM","UNAVAILABLE"),("VOLATILITY","UNAVAILABLE"),("VOLUME","UNAVAILABLE"),("LEVELS","UNAVAILABLE"),("PATTERNS","UNAVAILABLE")),category_strengths=(("TREND",0.),("MOMENTUM",0.),("VOLATILITY",0.),("VOLUME",0.),("LEVELS",0.),("PATTERNS",0.)),blockers=_unique(blocked))
    from .trend import evaluate_trend_intelligence
    from .momentum import evaluate_momentum_intelligence
    from .volatility import evaluate_volatility_intelligence
    from .levels import evaluate_level_intelligence
    from .patterns import evaluate_pattern_intelligence
    results=(evaluate_trend_intelligence(candle_series,policy),evaluate_momentum_intelligence(candle_series,policy),evaluate_volatility_intelligence(candle_series,policy),evaluate_level_intelligence(candle_series,policy),evaluate_pattern_intelligence(candle_series,policy))
    trend,momentum,volatility,levels,patterns=results; indicators=tuple(x for result in results for x in result["indicators"])
    if len({x.indicator_name for x in indicators})!=len(indicators):raise ValueError("Duplicate technical indicator name.")
    volume=[x for x in volatility["indicators"] if x.indicator_name in {"VOLUME_AVERAGE","VWAP"} and x.status=="VALID"]
    if len(volume)<2: volume_state,volume_strength,volume_warning="UNAVAILABLE",0.,"volume_evidence_unavailable"
    else: volume_state="SUPPORTIVE" if all(x.signal in {"HIGH","BULLISH"} for x in volume) else "WEAK" if any(x.signal in {"LOW","BEARISH"} for x in volume) else "NEUTRAL";volume_strength=sum(1 for x in volume if x.signal in {"HIGH","BULLISH"})/len(volume);volume_warning=None
    signals=[x.signal for x in indicators if x.status=="VALID"];warnings=[*timeframe_evidence.warnings,*[w for r in results for w in r["warnings"]]]+([volume_warning] if volume_warning else []);blockers=[*timeframe_evidence.blockers,*[b for r in results for b in r["blockers"]]]
    legacy_volume="UNAVAILABLE" if volume_state=="UNAVAILABLE" else "NEUTRAL"
    legacy_volatility="UNAVAILABLE" if volatility["bias"]=="UNAVAILABLE" else "NEUTRAL"
    return TimeframeTechnicalEvidenceV1(**base,indicators=indicators,category_biases=(("TREND",trend["bias"]),("MOMENTUM",momentum["bias"]),("VOLATILITY",legacy_volatility),("VOLUME",legacy_volume),("LEVELS",levels["bias"]),("PATTERNS",patterns["bias"])),category_strengths=(("TREND",trend["strength"]),("MOMENTUM",momentum["strength"]),("VOLATILITY",volatility["strength"]),("VOLUME",volume_strength),("LEVELS",levels["strength"]),("PATTERNS",patterns["strength"])),trend_bias=trend["bias"],momentum_bias=momentum["bias"],volatility_state="EXPANDING" if volatility["strength"] else "NORMAL",volume_state=volume_state,level_state={"BULLISH":"ABOVE_RESISTANCE","BEARISH":"BELOW_SUPPORT","NEUTRAL":"INSIDE_RANGE","UNAVAILABLE":"UNAVAILABLE"}[levels["bias"]],pattern_state="NONE" if patterns["bias"]=="NEUTRAL" else patterns["bias"],trend_strength=trend["strength"],momentum_strength=momentum["strength"],volatility_strength=volatility["strength"],volume_strength=volume_strength,level_strength=levels["strength"],pattern_strength=patterns["strength"],bullish_evidence_count=signals.count("BULLISH"),bearish_evidence_count=signals.count("BEARISH"),neutral_evidence_count=sum(x in {"NEUTRAL","NONE"} for x in signals),valid_indicator_count=sum(x.status=="VALID" for x in indicators),unavailable_indicator_count=sum(x.status!="VALID" for x in indicators),blockers=_unique(blockers),warnings=_unique(warnings))
