"""Deterministic non-renormalized technical aggregation."""
from __future__ import annotations
from datetime import datetime,timezone
def aggregate_technical_intelligence(*,multi_timeframe_snapshot,multi_timeframe_quality_result,timeframe_technical_evidence,policy=None,clock=None,technical_intelligence_result_id_factory=None):
 from services.contracts import MultiTimeframeSnapshotV1,MultiTimeframeQualityResultV1,TimeframeTechnicalEvidenceV1,TechnicalIntelligencePolicyV1,TechnicalIntelligenceResultV1,DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(multi_timeframe_snapshot,MultiTimeframeSnapshotV1) or not isinstance(multi_timeframe_quality_result,MultiTimeframeQualityResultV1) or not isinstance(timeframe_technical_evidence,tuple):raise ValueError("Invalid aggregation inputs.")
 if policy is None:policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(policy,TechnicalIntelligencePolicyV1) or any(not isinstance(x,TimeframeTechnicalEvidenceV1) for x in timeframe_technical_evidence) or (clock is not None and not callable(clock)) or (technical_intelligence_result_id_factory is not None and not callable(technical_intelligence_result_id_factory)):raise ValueError("Invalid aggregation controls.")
 if multi_timeframe_quality_result.multi_timeframe_snapshot_id!=multi_timeframe_snapshot.multi_timeframe_snapshot_id or tuple(x.timeframe for x in timeframe_technical_evidence)!=policy.required_timeframes or tuple(multi_timeframe_snapshot.required_timeframes)!=policy.required_timeframes:raise ValueError("Aggregation linkage mismatch.")
 now=(clock() if clock else datetime.now(timezone.utc));
 if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError("Clock must be timezone-aware.")
 rid=(technical_intelligence_result_id_factory or (lambda:"technical-"+multi_timeframe_snapshot.multi_timeframe_snapshot_id))()
 if not isinstance(rid,str) or not rid.strip():raise ValueError("Invalid technical result id.")
 status=multi_timeframe_quality_result.quality_status;block={"FAILED","UNSUPPORTED","MALFORMED","FUTURE","MISSING_TIMEFRAMES","STALE"};
 if status in {"INCOMPLETE","INSUFFICIENT_HISTORY"} and getattr(policy,"incomplete_timeframe_behavior" if status=="INCOMPLETE" else "insufficient_history_behavior")=="BLOCK":block.add(status)
 blocking=status in block
 scores=[]
 for e in timeframe_technical_evidence:
  score=(.25*e.trend_strength*(1 if e.trend_bias=="BULLISH" else -1 if e.trend_bias=="BEARISH" else 0)+.2*e.momentum_strength*(1 if e.momentum_bias=="BULLISH" else -1 if e.momentum_bias=="BEARISH" else 0)+.15*e.level_strength*(1 if e.level_state=="ABOVE_RESISTANCE" else -1 if e.level_state=="BELOW_SUPPORT" else 0)+.1*e.pattern_strength*(1 if e.pattern_state=="BULLISH" else -1 if e.pattern_state=="BEARISH" else 0));scores.append(score)
 weighted=sum(score*weight for score,(_,weight) in zip(scores,policy.timeframe_weights));bull=tuple(t for t,s in zip(policy.required_timeframes,scores) if s>=.1);bear=tuple(t for t,s in zip(policy.required_timeframes,scores) if s<=-.1);unavailable=tuple(e.timeframe for e,s in zip(timeframe_technical_evidence,scores) if e.blockers or (e.valid_indicator_count==0));neutral=tuple(t for t in policy.required_timeframes if t not in bull+bear+unavailable)
 mixed=bool(bull and bear);bias="MIXED" if mixed else "BULLISH" if weighted>=.15 else "BEARISH" if weighted<=-.15 else "NEUTRAL";final_status="READY_WITH_WARNINGS" if status=="READY_WITH_WARNINGS" or mixed or status=="MISALIGNED" else "READY";blockers=tuple(multi_timeframe_quality_result.blockers);warnings=tuple(multi_timeframe_quality_result.warnings)
 if status=="MISALIGNED":
  if policy.conflicting_timeframe_behavior=="BLOCK": final_status="CONFLICTING";bias="UNAVAILABLE";weighted=0.;blockers=blockers or ("multi_timeframe_quality_misaligned",)
  else: final_status="READY_WITH_WARNINGS";warnings=tuple(dict.fromkeys(warnings+blockers+("multi_timeframe_quality_misaligned",)));blockers=()
 if blocking:final_status=status;bias="UNAVAILABLE";weighted=0.;blockers=blockers or ("multi_timeframe_quality_"+status.lower(),)
 return TechnicalIntelligenceResultV1(rid,now,multi_timeframe_snapshot.multi_timeframe_snapshot_id,multi_timeframe_quality_result.multi_timeframe_quality_result_id,multi_timeframe_snapshot.underlying_symbol,multi_timeframe_snapshot.exchange,timeframe_technical_evidence,final_status,bias,abs(weighted),blockers,warnings,required_timeframes=policy.required_timeframes,bullish_timeframes=bull,bearish_timeframes=bear,neutral_timeframes=neutral,unavailable_timeframes=unavailable,aligned_timeframes=tuple(t for t in policy.required_timeframes if t not in unavailable),conflicting_timeframes=bear if bias=="BULLISH" else bull if bias=="BEARISH" else bull+bear,valid_indicator_count=sum(e.valid_indicator_count for e in timeframe_technical_evidence),unavailable_indicator_count=sum(e.unavailable_indicator_count for e in timeframe_technical_evidence))
