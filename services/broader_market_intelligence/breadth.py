"""Pure breadth classification over normalized supplied counts."""
from __future__ import annotations
from datetime import datetime
from services.contracts.broader_market_intelligence_policy_v1 import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,BroaderMarketIntelligencePolicyV1
from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
def _unavailable(snapshot,created_at,evidence_id,status,message):
 return MarketBreadthEvidenceV1(evidence_id,created_at,snapshot.underlying_symbol,snapshot.exchange,snapshot.source_id,snapshot.source_timestamp,None,None,None,None,0,0.,None,"UNAVAILABLE",0.,"UNAVAILABLE",snapshot.heavyweight_contribution_state,status,blockers=(message,),warnings=snapshot.warnings)
def evaluate_market_breadth(*,breadth_snapshot:MarketBreadthSnapshotV1,policy:BroaderMarketIntelligencePolicyV1=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,created_at:datetime,evidence_id:str)->MarketBreadthEvidenceV1:
 """Evaluate supplied breadth; ratio is advances/declines when declines exist."""
 if not isinstance(breadth_snapshot,MarketBreadthSnapshotV1):raise TypeError("breadth_snapshot must be a MarketBreadthSnapshotV1")
 if not isinstance(policy,BroaderMarketIntelligencePolicyV1):raise TypeError("policy must be a BroaderMarketIntelligencePolicyV1")
 if not isinstance(created_at,datetime):raise TypeError("created_at must be a datetime")
 if created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(evidence_id,str) or not evidence_id.strip():raise ValueError("evidence_id must be non-empty")
 age=(created_at-breadth_snapshot.source_timestamp).total_seconds()
 if age>policy.maximum_breadth_age_seconds:
  return _unavailable(breadth_snapshot,created_at,evidence_id,"STALE" if policy.require_breadth_evidence else "UNAVAILABLE","breadth source evidence is stale")
 if age < -policy.future_timestamp_tolerance_seconds:return _unavailable(breadth_snapshot,created_at,evidence_id,"BLOCKED","breadth source timestamp exceeds future tolerance")
 counts=(breadth_snapshot.advance_count,breadth_snapshot.decline_count,breadth_snapshot.unchanged_count,breadth_snapshot.total_count)
 if any(v is None for v in counts):return _unavailable(breadth_snapshot,created_at,evidence_id,"UNAVAILABLE","breadth counts are unavailable")
 advance,decline,unchanged,total=counts
 if advance+decline+unchanged!=total or breadth_snapshot.covered_count>total:return _unavailable(breadth_snapshot,created_at,evidence_id,"BLOCKED","breadth counts are internally inconsistent")
 if total==0 or breadth_snapshot.covered_count==0:return _unavailable(breadth_snapshot,created_at,evidence_id,"UNAVAILABLE","breadth coverage is unavailable")
 coverage=breadth_snapshot.covered_count/total
 if coverage<policy.minimum_breadth_coverage_ratio:return _unavailable(breadth_snapshot,created_at,evidence_id,"UNAVAILABLE","breadth coverage is below policy minimum")
 if breadth_snapshot.is_partial:return _unavailable(breadth_snapshot,created_at,evidence_id,"BLOCKED","breadth snapshot is partial")
 ratio=advance/decline if decline>0 else None
 if decline==0 and advance>0:bias="BULLISH"
 elif ratio is None:bias="NEUTRAL"
 elif ratio>=policy.bullish_advance_decline_ratio:bias="BULLISH"
 elif ratio<=policy.bearish_advance_decline_ratio:bias="BEARISH"
 else:bias="NEUTRAL"
 distance=1. if decline==0 and advance>0 else (ratio-policy.bullish_advance_decline_ratio)/(ratio+policy.bullish_advance_decline_ratio) if bias=="BULLISH" and ratio is not None else (policy.bearish_advance_decline_ratio-ratio)/(policy.bearish_advance_decline_ratio+max(ratio,1e-12)) if bias=="BEARISH" and ratio is not None else 0.
 strength=min(1.,max(0.01,coverage*(.1+.9*max(0.,distance))))
 if breadth_snapshot.heavyweight_contribution_state=="CONFIRMS":strength=min(1.,strength+.1)
 warnings=list(breadth_snapshot.warnings)
 if breadth_snapshot.heavyweight_contribution_state=="CONTRADICTS":
  if policy.block_on_heavyweight_opposition:return _unavailable(breadth_snapshot,created_at,evidence_id,"BLOCKED","heavyweight contribution contradicts breadth")
  warnings.append("heavyweight contribution contradicts breadth")
 if policy.require_heavyweight_confirmation and breadth_snapshot.heavyweight_contribution_state!="CONFIRMS":return _unavailable(breadth_snapshot,created_at,evidence_id,"UNAVAILABLE","heavyweight confirmation is required")
 participation="BROAD" if coverage>=.9 else "MODERATE" if coverage>=policy.minimum_breadth_coverage_ratio else "NARROW"
 return MarketBreadthEvidenceV1(evidence_id,created_at,breadth_snapshot.underlying_symbol,breadth_snapshot.exchange,breadth_snapshot.source_id,breadth_snapshot.source_timestamp,advance,decline,unchanged,total,breadth_snapshot.covered_count,coverage,ratio,bias,strength,participation,breadth_snapshot.heavyweight_contribution_state,"READY_WITH_WARNINGS" if warnings else "READY",warnings=tuple(warnings))
