"""Immutable normalized input for a future four-market opportunity ranker."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity
from .trade_opportunity_v1 import TradeOpportunityV1
from .canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from .market_session_validation_v1 import MarketSessionValidationV1
from .broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from .external_market_context_result_v1 import ExternalMarketContextResultV1

_STATUS={"READY","READY_WITH_WARNINGS","CONFLICTING","BLOCKED","UNAVAILABLE"}
_RESTRICTION={"OPEN","WARNING","BLOCKED","SESSION_OWNED","UNAVAILABLE"}
_QUALITY={"GOOD","DEGRADED","STALE","UNAVAILABLE"}; _FRESH={"FRESH","STALE","FUTURE","MIXED","UNAVAILABLE"}
_SCORES=("opportunity_confidence","regime_suitability_score","technical_confirmation_score","option_chain_confirmation_score","broader_market_confirmation_score","external_context_confirmation_score","data_quality_score","liquidity_score","execution_quality_score")
_FLAGS=("trade_opportunity_available","option_chain_available","broader_market_available","external_context_available","liquidity_available","execution_quality_available")

def _text(v,n):
 if type(v) is not str or not (v:=" ".join(v.split())): raise ValueError(n)
 return v
def _items(v,n):
 if not isinstance(v,tuple): raise TypeError(n)
 seen=[]
 for x in v:
  x=_text(x,n).upper()
  if x not in seen: seen.append(x)
 return tuple(seen)
def _freeze(v):
 if isinstance(v,dict): return MappingProxyType({k:_freeze(x) for k,x in v.items()})
 if isinstance(v,list): return tuple(_freeze(x) for x in v)
 return v
def _serialize(v):
 if isinstance(v,datetime): return v.isoformat()
 if isinstance(v,Mapping): return {k:_serialize(x) for k,x in v.items()}
 if isinstance(v,tuple): return [_serialize(x) for x in v]
 if hasattr(v,"to_dict"): return v.to_dict()
 return v

@dataclass(frozen=True,slots=True)
class MarketOpportunityCandidateV1:
 candidate_id:str; evaluated_at:datetime; underlying_symbol:str; exchange:str
 market_regime:CanonicalMarketRegimeResultV1; market_session_validation:MarketSessionValidationV1
 candidate_status:str; analysis_allowed:bool; new_entries_allowed:bool
 opportunity_confidence:float; regime_suitability_score:float; technical_confirmation_score:float; option_chain_confirmation_score:float; broader_market_confirmation_score:float; external_context_confirmation_score:float; data_quality_score:float; liquidity_score:float; execution_quality_score:float
 trade_opportunity_available:bool; option_chain_available:bool; broader_market_available:bool; external_context_available:bool; liquidity_available:bool; execution_quality_available:bool
 entry_restriction_state:str; data_quality_state:str; freshness_state:str
 trade_opportunity:TradeOpportunityV1|None=None; broader_market_intelligence:BroaderMarketIntelligenceResultV1|None=None; external_market_context:ExternalMarketContextResultV1|None=None
 supporting_evidence:tuple[str,...]=(); contradictions:tuple[str,...]=(); blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); source_timestamps:Mapping[str,datetime]=None; metadata:Mapping[str,Any]=None; execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="1.0"
 def __post_init__(self):
  object.__setattr__(self,"candidate_id",_text(self.candidate_id,"candidate_id"))
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None: raise ValueError("evaluated_at")
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if not identity: raise ValueError("identity")
  object.__setattr__(self,"underlying_symbol",identity[0]); object.__setattr__(self,"exchange",identity[1])
  for n,t in (("market_regime",CanonicalMarketRegimeResultV1),("market_session_validation",MarketSessionValidationV1),("trade_opportunity",TradeOpportunityV1),("broader_market_intelligence",BroaderMarketIntelligenceResultV1),("external_market_context",ExternalMarketContextResultV1)):
   child=getattr(self,n)
   if child is None and n not in {"trade_opportunity","broader_market_intelligence","external_market_context"}: raise TypeError(n)
   if child is not None and type(child) is not t: raise TypeError(n)
   if child is not None and (getattr(child,"underlying_symbol",getattr(child,"symbol",None)),child.exchange)!=identity: raise ValueError(n)
   if child is not None and not isinstance(getattr(child,"created_at",getattr(child,"evaluated_at",None)),datetime): raise ValueError(n)
  for n in _SCORES:
   v=getattr(self,n)
   if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or not 0<=float(v)<=1: raise ValueError(n)
   object.__setattr__(self,n,float(v))
  for n in _FLAGS+("analysis_allowed","new_entries_allowed"):
   if type(getattr(self,n)) is not bool: raise TypeError(n)
  if not self.analysis_allowed and self.new_entries_allowed: raise ValueError("analysis_allowed")
  for n,allowed in (("candidate_status",_STATUS),("entry_restriction_state",_RESTRICTION),("data_quality_state",_QUALITY),("freshness_state",_FRESH)):
   v=_text(getattr(self,n),n).upper()
   if v not in allowed: raise ValueError(n)
   object.__setattr__(self,n,v)
  if self.trade_opportunity_available != (self.trade_opportunity is not None) or self.broader_market_available != (self.broader_market_intelligence is not None) or self.external_context_available != (self.external_market_context is not None): raise ValueError("availability")
  for flag,score in (("option_chain_available","option_chain_confirmation_score"),("liquidity_available","liquidity_score"),("execution_quality_available","execution_quality_score")):
   if not getattr(self,flag) and getattr(self,score)!=0: raise ValueError("availability")
  if not self.broader_market_available and self.broader_market_confirmation_score!=0 or not self.external_context_available and self.external_context_confirmation_score!=0 or not self.trade_opportunity_available and self.opportunity_confidence!=0: raise ValueError("availability")
  for n in ("supporting_evidence","contradictions","blockers","warnings"): object.__setattr__(self,n,_items(getattr(self,n),n))
  if self.entry_restriction_state=="BLOCKED" and self.new_entries_allowed: raise ValueError("restriction")
  if self.candidate_status=="READY" and (self.blockers or self.warnings or self.contradictions): raise ValueError("READY")
  if self.candidate_status=="READY_WITH_WARNINGS" and (not self.warnings or self.blockers or self.contradictions): raise ValueError("READY_WITH_WARNINGS")
  if self.candidate_status=="CONFLICTING" and (not self.contradictions or self.blockers): raise ValueError("CONFLICTING")
  if self.candidate_status=="BLOCKED" and (not self.blockers or self.new_entries_allowed): raise ValueError("BLOCKED")
  if self.candidate_status=="UNAVAILABLE" and (not (self.blockers or self.warnings) or self.new_entries_allowed): raise ValueError("UNAVAILABLE")
  if self.data_quality_state=="UNAVAILABLE" and self.data_quality_score!=0: raise ValueError("data_quality")
  unavailable=not all(getattr(self,n) for n in _FLAGS)
  if self.freshness_state=="UNAVAILABLE" and not unavailable: raise ValueError("freshness")
  if self.freshness_state in {"STALE","FUTURE"} and not (self.warnings or self.blockers): raise ValueError("freshness")
  timestamps=self.source_timestamps if self.source_timestamps is not None else {}
  if not isinstance(timestamps,Mapping): raise TypeError("source_timestamps")
  normalized={_text(k,"source").upper():v for k,v in timestamps.items()}
  if any(not isinstance(v,datetime) or v.tzinfo is None for v in normalized.values()): raise ValueError("source_timestamps")
  object.__setattr__(self,"source_timestamps",MappingProxyType(dict(sorted(normalized.items()))))
  metadata=self.metadata if self.metadata is not None else {}
  if not isinstance(metadata,Mapping): raise TypeError("metadata")
  try: safe=json.loads(json.dumps(dict(metadata),sort_keys=True,allow_nan=False))
  except (TypeError,ValueError) as exc: raise ValueError("metadata") from exc
  object.__setattr__(self,"metadata",_freeze(safe))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or not _text(self.schema_version,"schema_version"): raise ValueError("execution")
 def to_dict(self):
  return {n:_serialize(getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict(); d.pop("candidate_id"); d.pop("evaluated_at"); return d
