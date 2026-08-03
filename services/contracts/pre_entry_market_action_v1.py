"""Immutable PAPER-only child pre-entry action projection."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

_IDENTITIES=frozenset({("NIFTY","NSE"),("SENSEX","BSE")});_ACTIONS=frozenset({"CALL","PUT","WAIT","UNAVAILABLE"});_DIRECTIONS=frozenset({"BULLISH","BEARISH","NEUTRAL","UNAVAILABLE","CONFLICTING"});_ELIGIBILITY=frozenset({"ELIGIBLE","INELIGIBLE","UNAVAILABLE","CONFLICTING"});_FORBIDDEN=frozenset({"api_key","apikey","secret","password","pin","authorization","access_token","refresh_token","jwt","raw_payload","provider_payload","raw_exception","exception_text"})
def _text(v,n):
 if not isinstance(v,str) or not (v:=v.strip()):raise ValueError(n)
 return v
def _messages(v,n):
 if not isinstance(v,tuple):raise TypeError(n)
 r=tuple(_text(x,n) for x in v)
 if len(set(r))!=len(r):raise ValueError(n)
 return r
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:raise ValueError(n)
 return v
@dataclass(frozen=True,slots=True)
class PreEntryMarketActionV1:
 action_id:str;underlying_symbol:str;exchange:str;cycle_id:str;observation_id:str;candidate_id:str|None;action:str;candidate_direction:str;candidate_eligibility:str;confidence:float;score:float;regime_suitability:str|None;selected_for_parent_comparison:bool;source_ledger_id:str|None;evaluated_at:datetime;blockers:tuple[str,...]=();warnings:tuple[str,...]=();reasons:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="pre_entry_market_action.v1"
 def __post_init__(self):
  for n in ("action_id","cycle_id","observation_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  identity=(_text(self.underlying_symbol,"underlying_symbol").upper(),_text(self.exchange,"exchange").upper())
  if identity not in _IDENTITIES:raise ValueError("identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  for n,allowed in (("action",_ACTIONS),("candidate_direction",_DIRECTIONS),("candidate_eligibility",_ELIGIBILITY)):
   v=_text(getattr(self,n),n).upper()
   if v not in allowed:raise ValueError(n)
   object.__setattr__(self,n,v)
  for n in ("confidence","score"):
   v=getattr(self,n)
   if isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(float(v)) or not 0<=float(v)<=100:raise ValueError(n)
   object.__setattr__(self,n,float(v))
  _aware(self.evaluated_at,"evaluated_at")
  if not isinstance(self.selected_for_parent_comparison,bool) or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="pre_entry_market_action.v1":raise ValueError("PAPER")
  if self.candidate_id is not None:object.__setattr__(self,"candidate_id",_text(self.candidate_id,"candidate_id"))
  if self.source_ledger_id is not None:object.__setattr__(self,"source_ledger_id",_text(self.source_ledger_id,"source_ledger_id"))
  for n in ("blockers","warnings","reasons"):object.__setattr__(self,n,_messages(getattr(self,n),n))
  if self.action in {"CALL","PUT"} and (self.candidate_id is None or self.candidate_eligibility!="ELIGIBLE" or self.blockers or self.confidence<=0 or self.score<=0):raise ValueError("entry action invariant")
  if self.action=="CALL" and self.candidate_direction!="BULLISH":raise ValueError("CALL direction")
  if self.action=="PUT" and self.candidate_direction!="BEARISH":raise ValueError("PUT direction")
  if self.action=="WAIT" and (self.blockers or not self.reasons or self.candidate_direction in {"BULLISH","BEARISH"} and self.candidate_eligibility=="ELIGIBLE"):raise ValueError("WAIT invariant")
  if self.action=="UNAVAILABLE" and (self.candidate_eligibility=="ELIGIBLE" or not (self.blockers or self.reasons) or self.confidence!=0 or self.score!=0):raise ValueError("UNAVAILABLE invariant")
  if not isinstance(self.metadata,Mapping) or any(not isinstance(k,str) or k.lower() in _FORBIDDEN for k in self.metadata):raise ValueError("metadata")
  try:json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False)
  except (TypeError,ValueError) as exc:raise ValueError("metadata") from exc
  object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))
 def to_dict(self):return {"action_id":self.action_id,"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"cycle_id":self.cycle_id,"observation_id":self.observation_id,"candidate_id":self.candidate_id,"action":self.action,"candidate_direction":self.candidate_direction,"candidate_eligibility":self.candidate_eligibility,"confidence":self.confidence,"score":self.score,"regime_suitability":self.regime_suitability,"selected_for_parent_comparison":self.selected_for_parent_comparison,"source_ledger_id":self.source_ledger_id,"evaluated_at":self.evaluated_at.isoformat(),"blockers":list(self.blockers),"warnings":list(self.warnings),"reasons":list(self.reasons),"metadata":dict(self.metadata),"execution_mode":self.execution_mode,"live_execution_eligible":self.live_execution_eligible,"schema_version":self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
