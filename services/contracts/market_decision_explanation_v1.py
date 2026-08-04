"""Immutable, typed, PAPER-only decision explanation contracts."""
from __future__ import annotations
import json
from dataclasses import dataclass,field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Mapping,Any
_IDENTITIES=frozenset({("NIFTY","NSE"),("SENSEX","BSE")});_CATEGORIES=frozenset({"SUPPORTING","OPPOSING","CONTRADICTION","BLOCKER","WARNING","QUALITY","SUITABILITY","INFORMATIONAL"});_DIRECTIONS=frozenset({"BULLISH","BEARISH","NEUTRAL","UNAVAILABLE","CONFLICTING"});_STATUS=frozenset({"READY","UNAVAILABLE","BLOCKED","CONFLICTING"});_FORBIDDEN=frozenset({"api_key","apikey","secret","password","pin","authorization","access_token","refresh_token","jwt","raw_payload","provider_payload","raw_exception","exception_text"})
def _text(v,n):
 if not isinstance(v,str) or not(v:=v.strip()):raise ValueError(n)
 return v
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:raise ValueError(n)
 return v
def _codes(v,n):
 if not isinstance(v,tuple):raise TypeError(n)
 r=tuple(_text(x,n) for x in v)
 if len(set(r))!=len(r):raise ValueError(n)
 return r
@dataclass(frozen=True,slots=True)
class MarketEvidenceExplanationEntryV1:
 explanation_entry_id:str;category:str;source_component:str;source_result_id:str|None;pillar_name:str|None;direction:str;status:str;priority:int;stable_reason_code:str;numeric_value:float|None;source_timestamp:datetime|None;evaluated_at:datetime;counted_in_confidence:bool;selected_for_summary:bool;metadata:Mapping[str,Any]=field(default_factory=dict)
 def __post_init__(self):
  for n in ("explanation_entry_id","source_component","stable_reason_code"):object.__setattr__(self,n,_text(getattr(self,n),n))
  for n,allowed in (("category",_CATEGORIES),("direction",_DIRECTIONS),("status",_STATUS)):
   v=_text(getattr(self,n),n).upper()
   if v not in allowed:raise ValueError(n)
   object.__setattr__(self,n,v)
  if not isinstance(self.priority,int) or not 0<=self.priority<=100 or not isinstance(self.counted_in_confidence,bool) or not isinstance(self.selected_for_summary,bool):raise ValueError("priority")
  if self.numeric_value is not None and (isinstance(self.numeric_value,bool) or not isinstance(self.numeric_value,(int,float)) or not isfinite(float(self.numeric_value)) or not -100<=float(self.numeric_value)<=100):raise ValueError("numeric_value")
  if self.source_timestamp is not None:_aware(self.source_timestamp,"source_timestamp")
  _aware(self.evaluated_at,"evaluated_at")
  if not isinstance(self.metadata,Mapping) or any(not isinstance(k,str) or k.lower() in _FORBIDDEN for k in self.metadata):raise ValueError("metadata")
  object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))
@dataclass(frozen=True,slots=True)
class MarketDecisionExplanationV1:
 explanation_id:str;underlying_symbol:str;exchange:str;cycle_id:str;observation_id:str;candidate_id:str|None;action_id:str|None;action:str;eligibility:str;direction:str;confidence:float;score:float;regime_suitability:str|None;entries:tuple[MarketEvidenceExplanationEntryV1,...];blockers:tuple[str,...]=();warnings:tuple[str,...]=();action_reason_codes:tuple[str,...]=();terminal_reason_codes:tuple[str,...]=();execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="market_decision_explanation.v1"
 def __post_init__(self):
  for n in ("explanation_id","cycle_id","observation_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  identity=(_text(self.underlying_symbol,"underlying_symbol").upper(),_text(self.exchange,"exchange").upper())
  if identity not in _IDENTITIES:raise ValueError("identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
  if self.action not in {"CALL","PUT","WAIT","UNAVAILABLE"} or self.eligibility not in {"ELIGIBLE","INELIGIBLE","UNAVAILABLE","CONFLICTING"} or self.direction not in _DIRECTIONS:raise ValueError("vocabulary")
  if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=100 for v in (self.confidence,self.score)):raise ValueError("score")
  if not isinstance(self.entries,tuple) or tuple(sorted(x.explanation_entry_id for x in self.entries))!=tuple(x.explanation_entry_id for x in self.entries):raise ValueError("entries")
  for n in ("blockers","warnings","action_reason_codes","terminal_reason_codes"):object.__setattr__(self,n,_codes(getattr(self,n),n))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_decision_explanation.v1":raise ValueError("PAPER")
 def to_dict(self):return {"explanation_id":self.explanation_id,"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"cycle_id":self.cycle_id,"observation_id":self.observation_id,"candidate_id":self.candidate_id,"action_id":self.action_id,"action":self.action,"eligibility":self.eligibility,"direction":self.direction,"confidence":self.confidence,"score":self.score,"regime_suitability":self.regime_suitability,"blockers":list(self.blockers),"warnings":list(self.warnings),"action_reason_codes":list(self.action_reason_codes),"terminal_reason_codes":list(self.terminal_reason_codes),"entries":[e.__dict__ if hasattr(e,"__dict__") else {"id":e.explanation_entry_id,"category":e.category,"reason":e.stable_reason_code} for e in self.entries]}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)

@dataclass(frozen=True,slots=True)
class TwoMarketDecisionExplanationV1:
 explanation_id:str;cycle_id:str;parent_decision_id:str;parent_status:str;parent_action:str;selected_market:str;selected_action:str|None;selected_candidate_id:str|None;winner_market:str|None;loser_market:str|None;winner_reason_codes:tuple[str,...];loser_reason_codes:tuple[str,...];comparison_reason_codes:tuple[str,...];tie_break_reason_codes:tuple[str,...];no_trade_reason_codes:tuple[str,...];nifty_explanation_id:str;sensex_explanation_id:str;invariant_status:str;blockers:tuple[str,...];warnings:tuple[str,...];evaluated_at:datetime;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="two_market_decision_explanation.v1"
 def __post_init__(self):
  for n in ("explanation_id","cycle_id","parent_decision_id","nifty_explanation_id","sensex_explanation_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  if self.parent_status not in {"SELECTED","NO_TRADE","UNAVAILABLE"} or self.parent_action not in {"CALL","PUT","NO_TRADE","UNAVAILABLE"} or self.selected_market not in {"NIFTY","SENSEX","NONE"} or self.invariant_status not in {"VALID","FAILED"}:raise ValueError("parent vocabulary")
  if self.selected_market=="NONE" and (self.winner_market is not None or self.parent_action not in {"NO_TRADE","UNAVAILABLE"}):raise ValueError("no selection invariant")
  if self.selected_market!="NONE" and (self.winner_market!=self.selected_market or self.selected_action not in {"CALL","PUT"} or self.parent_action!=self.selected_action or self.selected_candidate_id is None):raise ValueError("selected invariant")
  for n in ("winner_reason_codes","loser_reason_codes","comparison_reason_codes","tie_break_reason_codes","no_trade_reason_codes","blockers","warnings"):object.__setattr__(self,n,_codes(getattr(self,n),n))
  _aware(self.evaluated_at,"evaluated_at")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="two_market_decision_explanation.v1":raise ValueError("PAPER")
 def to_dict(self):return {"explanation_id":self.explanation_id,"cycle_id":self.cycle_id,"parent_decision_id":self.parent_decision_id,"parent_status":self.parent_status,"parent_action":self.parent_action,"selected_market":self.selected_market,"selected_action":self.selected_action,"selected_candidate_id":self.selected_candidate_id,"winner_market":self.winner_market,"loser_market":self.loser_market,"winner_reason_codes":list(self.winner_reason_codes),"loser_reason_codes":list(self.loser_reason_codes),"comparison_reason_codes":list(self.comparison_reason_codes),"tie_break_reason_codes":list(self.tie_break_reason_codes),"no_trade_reason_codes":list(self.no_trade_reason_codes),"nifty_explanation_id":self.nifty_explanation_id,"sensex_explanation_id":self.sensex_explanation_id,"invariant_status":self.invariant_status,"blockers":list(self.blockers),"warnings":list(self.warnings),"evaluated_at":self.evaluated_at.isoformat(),"execution_mode":self.execution_mode,"live_execution_eligible":self.live_execution_eligible,"schema_version":self.schema_version}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
