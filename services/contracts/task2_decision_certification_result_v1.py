"""Immutable, safe output for one deterministic Task 2 certification fixture."""
import hashlib,json
from dataclasses import asdict,dataclass
from datetime import datetime

def _text(value,name):
 if type(value) is not str or not value.strip():raise ValueError(name)
 return value.strip()
def _aware(value,name):
 if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:raise ValueError(name)
 return value
@dataclass(frozen=True,slots=True)
class Task2MarketDecisionCertificationV1:
 market_certification_id:str;scenario_id:str;underlying_symbol:str;exchange:str;parent_cycle_id:str;observation_id:str;candidate_id:str|None;canonical_evidence_status:str;pillar_contribution_count:int;ordered_pillar_names:tuple[str,...];pillar_statuses:tuple[str,...];pillar_provenance_summary:tuple[str,...];confidence_ledger_id:str|None;confidence_ledger_status:str;legacy_confidence:float;ledger_confidence:float;confidence_delta:float;legacy_score:float;ledger_score:float;score_delta:float;pre_entry_action_id:str|None;pre_entry_action:str;child_explanation_id:str|None;child_explanation_status:str;terminal_status:str;terminal_reason_codes:tuple[str,...];blockers:tuple[str,...];warnings:tuple[str,...];evaluated_at:datetime
 def __post_init__(self):
  for n in ("market_certification_id","scenario_id","parent_cycle_id","observation_id","canonical_evidence_status","confidence_ledger_status","pre_entry_action","child_explanation_status","terminal_status"):object.__setattr__(self,n,_text(getattr(self,n),n))
  identity=(_text(self.underlying_symbol,"underlying_symbol").upper(),_text(self.exchange,"exchange").upper())
  if identity not in {("NIFTY","NSE"),("SENSEX","BSE")}:raise ValueError("market identity")
  object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1]);_aware(self.evaluated_at,"evaluated_at")
  if self.pillar_contribution_count<0 or self.pillar_contribution_count!=len(self.ordered_pillar_names):raise ValueError("pillar count")
  for n in ("legacy_confidence","ledger_confidence","legacy_score","ledger_score"):
   if type(getattr(self,n)) not in (int,float) or not 0<=getattr(self,n)<=100:raise ValueError(n)
@dataclass(frozen=True,slots=True)
class Task2DecisionCertificationResultV1:
 certification_id:str;scenario_id:str;parent_cycle_id:str;nifty:Task2MarketDecisionCertificationV1;sensex:Task2MarketDecisionCertificationV1;parent_decision_id:str;parent_decision_status:str;selected_market:str;parent_action:str;parent_explanation_id:str;comparison_reason_codes:tuple[str,...];winner_reason_codes:tuple[str,...];loser_reason_codes:tuple[str,...];no_trade_reason_codes:tuple[str,...];invariant_status:str;certification_status:str;certification_failure_codes:tuple[str,...];call_counts:tuple[tuple[str,int],...];safety_counters:tuple[tuple[str,int],...];deterministic_checksum:str;evaluated_at:datetime;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="task2_decision_certification_result.v1"
 def __post_init__(self):
  for n in ("certification_id","scenario_id","parent_cycle_id","parent_decision_id","parent_decision_status","selected_market","parent_action","parent_explanation_id","invariant_status","certification_status","deterministic_checksum"):object.__setattr__(self,n,_text(getattr(self,n),n))
  if type(self.nifty) is not Task2MarketDecisionCertificationV1 or type(self.sensex) is not Task2MarketDecisionCertificationV1:raise TypeError("markets")
  if (self.nifty.underlying_symbol,self.sensex.underlying_symbol)!=("NIFTY","SENSEX") or self.nifty.parent_cycle_id!=self.parent_cycle_id or self.sensex.parent_cycle_id!=self.parent_cycle_id:raise ValueError("nested identity")
  _aware(self.evaluated_at,"evaluated_at")
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="task2_decision_certification_result.v1":raise ValueError("PAPER")
 def to_json(self):return json.dumps(asdict(self),default=str,sort_keys=True,separators=(",",":"))
 def semantic_checksum(self):return hashlib.sha256(self.to_json().encode()).hexdigest()
