"""Pure aggregate of supplied broader-market evidence; no raw-data handling."""
from __future__ import annotations
from datetime import datetime
from services.core.market_identity import normalize_market_identity
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
from services.contracts.market_breadth_evidence_v1 import MarketBreadthEvidenceV1
from services.contracts.volatility_context_v1 import VolatilityContextV1
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.broader_market_intelligence_policy_v1 import DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,BroaderMarketIntelligencePolicyV1
def _unique(*groups):
 return tuple(dict.fromkeys(x for group in groups for x in group))
def evaluate_broader_market_intelligence(*,underlying_symbol:str,exchange:str,cross_market_evidence:tuple[CrossMarketEvidenceV1,...],breadth_evidence:MarketBreadthEvidenceV1|None,volatility_context:VolatilityContextV1|None,policy:BroaderMarketIntelligencePolicyV1=DEFAULT_BROADER_MARKET_INTELLIGENCE_POLICY,created_at:datetime,result_id:str)->BroaderMarketIntelligenceResultV1:
 identity=normalize_market_identity(underlying_symbol,exchange)
 if identity is None:raise ValueError("unsupported market identity")
 if not isinstance(cross_market_evidence,tuple):raise TypeError("cross_market_evidence must be a tuple")
 if not isinstance(policy,BroaderMarketIntelligencePolicyV1):raise TypeError("policy must be a BroaderMarketIntelligencePolicyV1")
 if not isinstance(created_at,datetime):raise TypeError("created_at must be a datetime")
 if created_at.tzinfo is None or created_at.utcoffset() is None:raise ValueError("created_at must be timezone-aware")
 if not isinstance(result_id,str) or not result_id.strip():raise ValueError("result_id must be non-empty")
 related=set();available=[];unavailable=[];warnings=[];blockers=[];contradictions=[];sources={}
 for item in cross_market_evidence:
  if not isinstance(item,CrossMarketEvidenceV1):raise TypeError("cross_market_evidence must contain CrossMarketEvidenceV1")
  if (item.primary_symbol,item.primary_exchange)!=identity:raise ValueError("cross-market child identity must match result")
  key=(item.related_symbol,item.related_exchange)
  if key in related:raise ValueError("duplicate cross-market relationship")
  related.add(key);sources[f"CROSS_MARKET:{item.related_symbol}"]=item.primary_source_timestamp
  if item.evidence_status in {"READY","READY_WITH_WARNINGS"}:available.append(("cross",item));warnings.extend(item.warnings)
  else:unavailable.append("CROSS_MARKET");warnings.extend(item.warnings);blockers.extend(item.blockers)
 required=policy.required_cross_market_relationships.get(identity,())
 if any(r not in related for r in required):blockers.append("required cross-market evidence is missing")
 if breadth_evidence is not None:
  if not isinstance(breadth_evidence,MarketBreadthEvidenceV1):raise TypeError("breadth_evidence must be MarketBreadthEvidenceV1 or None")
  if (breadth_evidence.underlying_symbol,breadth_evidence.exchange)!=identity:raise ValueError("breadth identity must match result")
  sources["BREADTH"]=breadth_evidence.source_timestamp
  if breadth_evidence.evidence_status in {"READY","READY_WITH_WARNINGS"}:available.append(("breadth",breadth_evidence));warnings.extend(breadth_evidence.warnings)
  else:unavailable.append("BREADTH");warnings.extend(breadth_evidence.warnings);blockers.extend(breadth_evidence.blockers)
 elif policy.warn_on_missing_optional_evidence:warnings.append("optional breadth evidence is unavailable")
 if volatility_context is not None:
  if not isinstance(volatility_context,VolatilityContextV1):raise TypeError("volatility_context must be VolatilityContextV1 or None")
  if (volatility_context.underlying_symbol,volatility_context.exchange)!=identity:raise ValueError("volatility identity must match result")
  sources["VOLATILITY"]=volatility_context.source_timestamp
  if volatility_context.context_status in {"READY","READY_WITH_WARNINGS"}:available.append(("volatility",volatility_context));warnings.extend(volatility_context.warnings)
  else:unavailable.append("VOLATILITY");warnings.extend(volatility_context.warnings);blockers.extend(volatility_context.blockers)
 elif policy.warn_on_missing_optional_evidence:warnings.append("optional volatility context is unavailable")
 if policy.require_cross_market_evidence and not any(name=="cross" for name,_ in available):blockers.append("mandatory cross-market evidence is unavailable")
 if policy.require_breadth_evidence and not any(name=="breadth" for name,_ in available):blockers.append("mandatory breadth evidence is unavailable")
 if policy.require_volatility_context and not any(name=="volatility" for name,_ in available):blockers.append("mandatory volatility context is unavailable")
 if len(available)<policy.minimum_available_component_count:blockers.append("available component count is below policy minimum")
 bull=bear=0.;strength_sum=weight_sum=0.
 for name,item in available:
  weight={"cross":policy.cross_market_weight,"breadth":policy.breadth_weight,"volatility":policy.volatility_weight}[name];strength=item.correlation_strength if name=="cross" else item.breadth_strength if name=="breadth" else item.volatility_strength
  strength_sum+=weight*strength;weight_sum+=weight
  bias=item.primary_direction if name=="cross" else item.breadth_bias if name=="breadth" else "NEUTRAL"
  if name=="cross" and item.confirmation_state!="CONFIRMING":contradictions.append("cross-market evidence is not confirming") if item.confirmation_state=="NOT_CONFIRMING" else None
  if name=="cross" and item.divergence_state=="DIRECTIONAL_DIVERGENCE":contradictions.append("cross-market directional divergence is observed")
  if bias=="BULLISH":bull+=weight*strength
  elif bias=="BEARISH":bear+=weight*strength
 if bull and bear:contradictions.append("available broader-market components oppose direction")
 raw=strength_sum/weight_sum if weight_sum else 0.;raw=min(1.,max(0.,raw+ (policy.confirmation_bonus if bull or bear else 0.) - (policy.divergence_penalty if contradictions else 0.) - policy.missing_optional_component_penalty*sum(x in {"BREADTH","VOLATILITY"} for x in unavailable)))
 blockers=_unique(tuple(blockers));warnings=_unique(tuple(warnings));contradictions=_unique(tuple(contradictions))
 if blockers:status="BLOCKED";bias="UNAVAILABLE";raw=0.;confirmation="UNAVAILABLE";divergence="UNAVAILABLE"
 elif contradictions:status="CONFLICTING";bias="CONFLICTING";confirmation="NOT_CONFIRMING";divergence="DIRECTIONAL_DIVERGENCE" if any("divergence" in x for x in contradictions) else "NONE"
 elif not available:status="UNAVAILABLE";bias="UNAVAILABLE";raw=0.;confirmation="UNAVAILABLE";divergence="UNAVAILABLE";blockers=("no broader-market evidence is available",)
 else:
  bias="BULLISH" if bull>bear else "BEARISH" if bear>bull else "NEUTRAL";confirmation="CONFIRMING" if any(n=="cross" and x.confirmation_state=="CONFIRMING" for n,x in available if n=="cross") else "PARTIAL";divergence="NONE";status="READY_WITH_WARNINGS" if warnings else "READY"
 supporting=tuple(("CROSS-MARKET EVIDENCE CONFIRMS "+x.primary_direction+" DIRECTION") for n,x in available if n=="cross" and x.confirmation_state=="CONFIRMING")+tuple(("MARKET BREADTH SUPPORTS "+x.breadth_bias+" DIRECTION") for n,x in available if n=="breadth" and x.breadth_bias in {"BULLISH","BEARISH"})
 return BroaderMarketIntelligenceResultV1(result_id,created_at,identity[0],identity[1],cross_market_evidence,breadth_evidence,volatility_context,status,bias,raw,confirmation,divergence,len(available),len(unavailable),supporting,contradictions,blockers,warnings,sources)
