from datetime import datetime,timezone
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.multi_timeframe_policy_v1 import DEFAULT_MULTI_TIMEFRAME_POLICY
from services.data_quality import DEFAULT_MARKET_DATA_FRESHNESS_POLICY
from .evidence_builder import build_timeframe_evidence
from .quality import evaluate_multi_timeframe_quality
def build_canonical_multi_timeframe_snapshot(*,candle_series_by_timeframe,policy=DEFAULT_MULTI_TIMEFRAME_POLICY,freshness_policy=DEFAULT_MARKET_DATA_FRESHNESS_POLICY,clock=None,timeframe_evidence_id_factory=None,quality_result_id_factory=None,snapshot_id_factory=None,multi_timeframe_quality_result_id_factory=None):
 series=tuple(candle_series_by_timeframe);now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not series:raise ValueError("candle series are required.")
 if len({s.timeframe for s in series})!=len(series) or len({(s.underlying_symbol,s.exchange) for s in series})!=1 or any(s.timeframe not in policy.required_timeframes for s in series):raise ValueError("Invalid multi-timeframe input.")
 ordered=tuple(sorted(series,key=lambda s:policy.required_timeframes.index(s.timeframe)));evidence=tuple(build_timeframe_evidence(s,policy=policy,freshness_policy=freshness_policy,clock=lambda:now,quality_result_id_factory=quality_result_id_factory,timeframe_evidence_id_factory=timeframe_evidence_id_factory) for s in ordered);symbol,exchange=ordered[0].underlying_symbol,ordered[0].exchange;missing=set(policy.required_timeframes)-{s.timeframe for s in ordered};snapshot=MultiTimeframeSnapshotV1((snapshot_id_factory or (lambda:"mtf-snapshot"))(),now,symbol,exchange,policy.required_timeframes,evidence,policy.anchor_timeframe,None,blockers=("missing_timeframes",) if missing else ());return snapshot,evaluate_multi_timeframe_quality(snapshot,policy=policy,clock=lambda:now,quality_result_id_factory=multi_timeframe_quality_result_id_factory)
