"""Immutable structural result for a future four-market ranking evaluator."""
from __future__ import annotations
import json,math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from .market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
_ID=(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE"));_EL={"ELIGIBLE","ELIGIBLE_WITH_WARNINGS","CONFLICTING","BLOCKED","UNAVAILABLE"};_TIE={"NO_TIE","TIE_RESOLVED","ALL_INELIGIBLE"}
def _txt(v,n):
 if type(v) is not str or not (v:=" ".join(v.split())):raise ValueError(n)
 return v
def _tuple(v,n):
 if not isinstance(v,tuple):raise TypeError(n)
 out=[]
 for x in v:
  x=_txt(x,n).upper()
  if x not in out:out.append(x)
 return tuple(out)
def _freeze(v):
 if isinstance(v,dict):return MappingProxyType({k:_freeze(x) for k,x in v.items()})
 if isinstance(v,list):return tuple(_freeze(x) for x in v)
 return v
def _child(v):return v.to_dict() if hasattr(v,"to_dict") else v
def _json_safe(v):
 if isinstance(v,datetime):return v.isoformat()
 if isinstance(v,Mapping):return {str(k):_json_safe(x) for k,x in v.items()}
 if isinstance(v,tuple):return [_json_safe(x) for x in v]
 if isinstance(v,list):return [_json_safe(x) for x in v]
 return v
@dataclass(frozen=True,slots=True)
class FourMarketOpportunityRankingResultV1:
 ranking_result_id:str;evaluated_at:datetime;candidates:tuple[MarketOpportunityCandidateV1,...];ordered_candidates:tuple[MarketOpportunityCandidateV1,...];selected_market:tuple[str,str]|None;selected_candidate:MarketOpportunityCandidateV1|None;rank_by_market:Mapping[tuple[str,str],int|None];score_by_market:Mapping[tuple[str,str],float|None];eligibility_by_market:Mapping[tuple[str,str],str];tie_state:str;selection_confidence:float
 blocked_markets:tuple[tuple[str,str],...]=();conflicting_markets:tuple[tuple[str,str],...]=();unavailable_markets:tuple[tuple[str,str],...]=();warning_markets:tuple[tuple[str,str],...]=();tied_markets:tuple[tuple[str,str],...]=();supporting_evidence:tuple[str,...]=();contradictions:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=None;metadata:Mapping[str,Any]=None;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="1.0"
 def __post_init__(self):
  object.__setattr__(self,"ranking_result_id",_txt(self.ranking_result_id,"ranking_result_id"))
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None:raise ValueError("evaluated_at")
  if not isinstance(self.candidates,tuple) or len(self.candidates)!=4 or any(type(c) is not MarketOpportunityCandidateV1 for c in self.candidates):raise TypeError("candidates")
  byid={(c.underlying_symbol,c.exchange):c for c in self.candidates}
  if set(byid)!=set(_ID):raise ValueError("candidates")
  object.__setattr__(self,"candidates",tuple(byid[i] for i in _ID))
  if not isinstance(self.ordered_candidates,tuple):raise TypeError("ordered_candidates")
  if any(type(candidate) is not MarketOpportunityCandidateV1 for candidate in self.ordered_candidates):raise ValueError("ordered_candidates")
  if any(not any(ordered is candidate for candidate in self.candidates) for ordered in self.ordered_candidates):raise ValueError("ordered_candidates")
  ordered_identities=tuple((candidate.underlying_symbol,candidate.exchange) for candidate in self.ordered_candidates)
  if len(ordered_identities)!=len(set(ordered_identities)):raise ValueError("ordered_candidates")
  if any(c.candidate_status in {"BLOCKED","UNAVAILABLE"} for c in self.ordered_candidates):raise ValueError("ordered_candidates")
  for n in ("rank_by_market","score_by_market","eligibility_by_market"):
   m=getattr(self,n)
   if not isinstance(m,Mapping) or set(m)!=set(_ID):raise ValueError(n)
  ranks=dict(self.rank_by_market);scores=dict(self.score_by_market);elig=dict(self.eligibility_by_market)
  if any(type(v) is not int and v is not None for v in ranks.values()) or any(v is not None and v<1 for v in ranks.values()):raise ValueError("rank_by_market")
  if any(v not in _EL for v in elig.values()):raise ValueError("eligibility_by_market")
  for i,c in enumerate(self.ordered_candidates,1):
   if ranks[(c.underlying_symbol,c.exchange)]!=i:raise ValueError("rank_by_market")
  for i in _ID:
   if ranks[i] is None:
    if i in ordered_identities:raise ValueError("rank_by_market")
   elif i not in ordered_identities:raise ValueError("rank_by_market")
  if sorted(v for v in ranks.values() if v is not None)!=list(range(1,len(self.ordered_candidates)+1)):raise ValueError("rank_by_market")
  for k,v in scores.items():
   if isinstance(v,bool) or v is not None and (not isinstance(v,(int,float)) or not math.isfinite(float(v)) or not 0<=float(v)<=1):raise ValueError("score_by_market")
   if v is not None:scores[k]=float(v)
  for i in _ID:
   if elig[i] in {"BLOCKED","UNAVAILABLE"} and ranks[i] is not None:raise ValueError("eligibility")
   if elig[i] in {"ELIGIBLE","ELIGIBLE_WITH_WARNINGS"} and ranks[i] is None:raise ValueError("eligibility")
  if (self.selected_market is None)!=(self.selected_candidate is None):raise ValueError("selection")
  if self.ordered_candidates and (self.selected_candidate is None or self.selected_candidate is not self.ordered_candidates[0] or self.selected_market!=(self.selected_candidate.underlying_symbol,self.selected_candidate.exchange)):raise ValueError("selection")
  if not self.ordered_candidates and self.selected_candidate is not None:raise ValueError("selection")
  if self.tie_state not in _TIE:raise ValueError("tie_state")
  if isinstance(self.selection_confidence,bool) or not isinstance(self.selection_confidence,(int,float)) or not math.isfinite(float(self.selection_confidence)) or not 0<=float(self.selection_confidence)<=1:raise ValueError("selection_confidence")
  object.__setattr__(self,"selection_confidence",float(self.selection_confidence))
  if self.tie_state=="ALL_INELIGIBLE" and (self.ordered_candidates or self.selected_candidate or self.selection_confidence!=0):raise ValueError("tie_state")
  for n,expected in (("blocked_markets","BLOCKED"),("conflicting_markets","CONFLICTING"),("unavailable_markets","UNAVAILABLE"),("warning_markets","ELIGIBLE_WITH_WARNINGS")):
   v=getattr(self,n)
   if not isinstance(v,tuple) or any(x not in _ID for x in v) or len(v)!=len(set(v)) or set(v)!={i for i in _ID if elig[i]==expected}:raise ValueError(n)
   object.__setattr__(self,n,tuple(i for i in _ID if i in v))
  for n in ("supporting_evidence","contradictions","blockers","warnings"):object.__setattr__(self,n,_tuple(getattr(self,n),n))
  ts=self.source_timestamps or {}
  if not isinstance(ts,Mapping) or any(type(k) is not str or not k or not isinstance(v,datetime) or v.tzinfo is None for k,v in ts.items()):raise ValueError("source_timestamps")
  object.__setattr__(self,"source_timestamps",MappingProxyType(dict(sorted(ts.items()))))
  try:safe=json.loads(json.dumps(dict(self.metadata or {}),sort_keys=True,allow_nan=False))
  except (TypeError,ValueError) as e:raise ValueError("metadata") from e
  object.__setattr__(self,"metadata",_freeze(safe))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or not _txt(self.schema_version,"schema_version"):raise ValueError("execution")
 def to_dict(self):
  return {"ranking_result_id":self.ranking_result_id,"evaluated_at":self.evaluated_at.isoformat(),"candidates":[_json_safe(_child(c)) for c in self.candidates],"ordered_candidates":[_json_safe(_child(c)) for c in self.ordered_candidates],"selected_market":list(self.selected_market) if self.selected_market else None,"selected_candidate":_json_safe(_child(self.selected_candidate)) if self.selected_candidate else None,"rank_by_market":[[list(i),_json_safe(self.rank_by_market[i])] for i in _ID],"score_by_market":[[list(i),_json_safe(self.score_by_market[i])] for i in _ID],"eligibility_by_market":[[list(i),_json_safe(self.eligibility_by_market[i])] for i in _ID],"tie_state":self.tie_state,"selection_confidence":self.selection_confidence,"blocked_markets":[list(i) for i in self.blocked_markets],"conflicting_markets":[list(i) for i in self.conflicting_markets],"unavailable_markets":[list(i) for i in self.unavailable_markets],"warning_markets":[list(i) for i in self.warning_markets],"tied_markets":[list(i) for i in self.tied_markets],"supporting_evidence":list(self.supporting_evidence),"contradictions":list(self.contradictions),"blockers":list(self.blockers),"warnings":list(self.warnings),"source_timestamps":_json_safe(self.source_timestamps),"metadata":_json_safe(self.metadata),"execution_mode":self.execution_mode,"live_execution_eligible":self.live_execution_eligible,"schema_version":self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
 def semantic_dict(self):
  d=self.to_dict();d.pop("ranking_result_id");d.pop("evaluated_at");return d
