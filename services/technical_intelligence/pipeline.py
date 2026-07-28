"""Supplied-evidence-only canonical technical pipeline."""
from __future__ import annotations
from datetime import datetime,timezone
def build_canonical_technical_intelligence(*,candle_series_by_timeframe,multi_timeframe_snapshot,multi_timeframe_quality_result,policy=None,clock=None,timeframe_technical_evidence_id_factory=None,technical_intelligence_result_id_factory=None):
 from services.contracts import MarketCandleSeriesV1,MultiTimeframeSnapshotV1,MultiTimeframeQualityResultV1,TechnicalIntelligencePolicyV1,DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(candle_series_by_timeframe,tuple) or not all(isinstance(x,MarketCandleSeriesV1) for x in candle_series_by_timeframe) or not isinstance(multi_timeframe_snapshot,MultiTimeframeSnapshotV1) or not isinstance(multi_timeframe_quality_result,MultiTimeframeQualityResultV1):raise ValueError("Invalid pipeline inputs.")
 if policy is None:policy=DEFAULT_TECHNICAL_INTELLIGENCE_POLICY
 if not isinstance(policy,TechnicalIntelligencePolicyV1) or (clock is not None and not callable(clock)):raise ValueError("Invalid pipeline policy.")
 lookup={x.timeframe:x for x in candle_series_by_timeframe}
 if len(lookup)!=len(candle_series_by_timeframe) or tuple(sorted(lookup))!=tuple(sorted(policy.required_timeframes)):raise ValueError("Series timeframe set mismatch.")
 evidence={x.timeframe:x for x in multi_timeframe_snapshot.timeframe_evidence};
 if tuple(evidence)!=policy.required_timeframes:raise ValueError("Snapshot timeframe evidence mismatch.")
 now=(clock() if clock else datetime.now(timezone.utc));
 if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError("Clock must be timezone-aware.")
 from .timeframe_analysis import analyze_timeframe_technical_evidence
 from .aggregation import aggregate_technical_intelligence
 values=tuple(analyze_timeframe_technical_evidence(candle_series=lookup[t],timeframe_evidence=evidence[t],policy=policy,clock=lambda:now,timeframe_technical_evidence_id_factory=timeframe_technical_evidence_id_factory) for t in policy.required_timeframes)
 return aggregate_technical_intelligence(multi_timeframe_snapshot=multi_timeframe_snapshot,multi_timeframe_quality_result=multi_timeframe_quality_result,timeframe_technical_evidence=values,policy=policy,clock=lambda:now,technical_intelligence_result_id_factory=technical_intelligence_result_id_factory)
