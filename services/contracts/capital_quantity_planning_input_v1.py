"""Immutable PAPER-only typed input for future capital/quantity planning."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from .canonical_trade_plan_input_v1 import CanonicalTradePlanInputV1
from .capital_quantity_planning_policy_v1 import CapitalQuantityPlanningPolicyV1
from .entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from .stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from .three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from .option_contract_selection_result_v1 import OptionContractSelectionResultV1
from .capital_quantity_trading_cost_policy_v1 import CapitalQuantityTradingCostPolicyV1
from .capital_quantity_trading_cost_evidence_v1 import CapitalQuantityTradingCostEvidenceV1
def _text(v,n):
 if type(v)is not str or not(v:=v.strip()):raise ValueError(n)
 return v
def _freeze(v):
 if v is None or type(v)in(bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_text(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in(tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class CapitalQuantityPlanningInputV1:
 planning_input_id:str;trade_plan_id:str;policy_id:str;canonical_trade_plan_input:CanonicalTradePlanInputV1;capital_quantity_policy:CapitalQuantityPlanningPolicyV1;entry_zone_result:EntryZoneEvaluationResultV1;stop_loss_result:StopLossEvaluationResultV1;three_target_result:ThreeTargetEvaluationResultV1;option_contract_selection_result:OptionContractSelectionResultV1;trading_cost_policy:CapitalQuantityTradingCostPolicyV1;trading_cost_evidence:CapitalQuantityTradingCostEvidenceV1|None;caller_supplied_per_lot_risk_amount:float|None;evaluated_at:datetime;input_source:str;blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('planning_input_id','trade_plan_id','policy_id','input_source'):object.__setattr__(self,n,_text(getattr(self,n),n))
  for n,t in (('canonical_trade_plan_input',CanonicalTradePlanInputV1),('capital_quantity_policy',CapitalQuantityPlanningPolicyV1),('entry_zone_result',EntryZoneEvaluationResultV1),('stop_loss_result',StopLossEvaluationResultV1),('three_target_result',ThreeTargetEvaluationResultV1),('option_contract_selection_result',OptionContractSelectionResultV1)):
   if type(getattr(self,n))is not t:raise TypeError(n)
  if type(self.trading_cost_policy)is not CapitalQuantityTradingCostPolicyV1:raise TypeError('trading_cost_policy')
  if self.trading_cost_evidence is not None and type(self.trading_cost_evidence)is not CapitalQuantityTradingCostEvidenceV1:raise TypeError('trading_cost_evidence')
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None:raise ValueError('evaluated_at')
  p=self.capital_quantity_policy
  if self.policy_id!=p.policy_id:raise ValueError('policy_id')
  cp=self.trading_cost_policy;ce=self.trading_cost_evidence
  if cp.calculation_mode=='CALLER_SUPPLIED_EVIDENCE' and ce is None:raise ValueError('trading_cost_evidence')
  if ce is not None:
   if (ce.planning_input_id,ce.trade_plan_id,ce.cost_policy_id,ce.option_selection_result_id)!=(self.planning_input_id,self.trade_plan_id,cp.cost_policy_id,self.option_contract_selection_result.selection_result_id):raise ValueError('trading_cost_evidence coherence')
   if ce.execution_mode!='PAPER' or ce.live_execution_eligible is not False:raise ValueError('trading_cost_evidence paper')
  if cp.execution_mode!='PAPER' or cp.live_execution_eligible is not False:raise ValueError('trading_cost_policy paper')
  upstream=(self.entry_zone_result,self.stop_loss_result,self.three_target_result,self.option_contract_selection_result)
  identity=(self.canonical_trade_plan_input.underlying_symbol,self.canonical_trade_plan_input.exchange,self.canonical_trade_plan_input.direction)
  if any((x.underlying_symbol,x.exchange,x.direction)!=identity for x in upstream):raise ValueError('identity')
  if any(getattr(x,'execution_mode',None)!='PAPER' or getattr(x,'live_execution_eligible',None) is not False for x in upstream) or self.canonical_trade_plan_input.execution_mode!='PAPER' or self.canonical_trade_plan_input.live_execution_eligible is not False:raise ValueError('paper coherence')
  v=self.caller_supplied_per_lot_risk_amount
  if p.risk_model=='PREMIUM_AT_RISK' and v is not None:raise ValueError('risk evidence')
  if p.risk_model=='CALLER_SUPPLIED_PER_LOT_RISK' and (type(v)not in (int,float) or isinstance(v,bool) or not math.isfinite(v) or v<=0):raise ValueError('risk evidence')
  if v is not None:object.__setattr__(self,'caller_supplied_per_lot_risk_amount',float(v))
  if not isinstance(self.blockers,tuple) or not isinstance(self.warnings,tuple):raise TypeError('diagnostics')
  for n in ('blockers','warnings'):object.__setattr__(self,n,tuple(dict.fromkeys(_text(x,n) for x in getattr(self,n))))
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('source_timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 @property
 def available_capital(self):return self.canonical_trade_plan_input.available_capital
 @property
 def risk_model(self):return self.capital_quantity_policy.risk_model
 @property
 def selected_option_contract(self):return self.option_contract_selection_result.selected_contract if self.option_contract_selection_result.status=='READY' else None
 @property
 def selected_lot_size(self):return self.option_contract_selection_result.selected_lot_size if self.selected_option_contract else None
 @property
 def estimated_one_lot_premium_cost(self):return self.option_contract_selection_result.estimated_one_lot_premium_cost if self.selected_option_contract else None
 @property
 def affordable_lot_count(self):return self.option_contract_selection_result.affordable_lot_count if self.selected_option_contract else None
 def to_dict(self):
  return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else getattr(self,n).to_dict() if n in {'canonical_trade_plan_input','capital_quantity_policy','entry_zone_result','stop_loss_result','three_target_result','option_contract_selection_result','trading_cost_policy'} else self.trading_cost_evidence.to_dict() if n=='trading_cost_evidence' and self.trading_cost_evidence else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'blockers','warnings'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('planning_input_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
