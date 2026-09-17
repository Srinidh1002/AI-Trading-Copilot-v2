"""Pure deterministic effective capital/risk constraint resolver."""
from __future__ import annotations
import json,math
from dataclasses import dataclass
from services.contracts.capital_quantity_planning_input_v1 import CapitalQuantityPlanningInputV1
@dataclass(frozen=True,slots=True)
class CapitalQuantityPlanningConstraintsV1:
 planning_input_id:str;trade_plan_id:str;policy_id:str;option_selection_result_id:str;available_capital:float;maximum_capital_utilization_fraction:float;minimum_reserve_capital:float;utilization_limited_capital:float;reserve_limited_capital:float;effective_deployable_capital:float;effective_reserved_capital:float;risk_model:str;maximum_risk_fraction:float|None;maximum_risk_amount:float|None;fraction_based_risk_budget:float|None;amount_based_risk_budget:float|None;effective_risk_budget:float|None;effective_per_lot_risk_amount:float|None;estimated_one_lot_premium_cost:float|None;upstream_affordable_lot_limit:int|None;deployable_capital_affordable_lot_limit:int|None;risk_based_lot_limit:int|None;effective_minimum_planned_lot_count:int;effective_maximum_planned_lot_count:int;is_coherent:bool;incoherence_codes:tuple[str,...];trading_cost_policy_id:str|None=None;trading_cost_calculation_mode:str|None=None;trading_cost_evidence_id:str|None=None;estimated_total_trading_cost:float|None=None;estimated_total_capital_requirement:float|None=None;cost_evidence_available:bool=False;cost_evidence_structurally_coherent:bool=False;execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def to_dict(self):return {n:list(getattr(self,n)) if n=='incoherence_codes' else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();d.pop('planning_input_id');return d
def resolve_capital_quantity_planning_constraints(planning_input):
 if type(planning_input)is not CapitalQuantityPlanningInputV1:raise TypeError('planning_input')
 p=planning_input.capital_quantity_policy;a=planning_input.available_capital;u=a*p.maximum_capital_utilization_fraction;r=max(a-p.minimum_reserve_capital,0.);d=min(u,r);codes=[]
 entry,stop,targets,selection=planning_input.entry_zone_result,planning_input.stop_loss_result,planning_input.three_target_result,planning_input.option_contract_selection_result
 for status,code in ((entry.status,'UPSTREAM_ENTRY_NOT_READY'),(stop.status,'UPSTREAM_STOP_NOT_READY'),(targets.status,'UPSTREAM_TARGETS_NOT_READY'),(selection.status,'UPSTREAM_CONTRACT_NOT_READY')):
  if status!='READY':codes.append(code)
 premium=planning_input.estimated_one_lot_premium_cost;affordable=planning_input.affordable_lot_count;lot=planning_input.selected_lot_size
 if premium is None:codes.append('ONE_LOT_PREMIUM_COST_UNAVAILABLE')
 if affordable is None:codes.append('UPSTREAM_AFFORDABLE_LIMIT_UNAVAILABLE')
 if lot is None:codes.append('LOT_SIZE_UNAVAILABLE')
 fb=None if p.maximum_risk_fraction is None else a*p.maximum_risk_fraction;ab=p.maximum_risk_amount;budget=min(x for x in (fb,ab) if x is not None) if fb is not None or ab is not None else None
 if budget is None:codes.append('RISK_BUDGET_UNAVAILABLE')
 risk=premium if p.risk_model=='PREMIUM_AT_RISK' else planning_input.caller_supplied_per_lot_risk_amount
 if risk is None:codes.append('PER_LOT_RISK_UNAVAILABLE')
 evidence=planning_input.trading_cost_evidence
 if evidence is None:codes.append('TRADING_COST_EVIDENCE_UNAVAILABLE')
 da=math.floor(d/premium) if premium else None;rl=math.floor(budget/risk) if budget is not None and risk else None
 return CapitalQuantityPlanningConstraintsV1(planning_input.planning_input_id,planning_input.trade_plan_id,p.policy_id,selection.selection_result_id,a,p.maximum_capital_utilization_fraction,p.minimum_reserve_capital,u,r,d,a-d,p.risk_model,p.maximum_risk_fraction,p.maximum_risk_amount,fb,ab,budget,risk,premium,affordable,da,rl,p.minimum_planned_lot_count,p.maximum_planned_lot_count,not codes,tuple(dict.fromkeys(codes)),planning_input.trading_cost_policy.cost_policy_id,planning_input.trading_cost_policy.calculation_mode,evidence.evidence_id if evidence else None,evidence.estimated_total_trading_cost if evidence else None,evidence.estimated_total_capital_requirement if evidence else None,evidence is not None,evidence is not None)
