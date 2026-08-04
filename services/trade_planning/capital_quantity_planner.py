"""Pure deterministic core capital/quantity planner; no execution or allocation."""
from __future__ import annotations
from services.contracts.capital_quantity_planning_input_v1 import CapitalQuantityPlanningInputV1
from services.contracts.capital_quantity_planning_result_v1 import CapitalQuantityPlanningResultV1
from .capital_quantity_planning_constraints import resolve_capital_quantity_planning_constraints
def _allocate_target_lots(total,weights):
 total_weight=sum(weights);exact=tuple(total*w/total_weight for w in weights);base=[int(x) for x in exact];order=tuple(i for i in sorted(range(3),key=lambda i:(-(exact[i]-base[i]),i)) if weights[i]>0);remaining=total-sum(base);assigned=[]
 for index in order:
  if remaining==0:break
  base[index]+=1;remaining-=1;assigned.append(index)
 return tuple(base),exact,tuple(exact[i]-int(exact[i]) for i in range(3)),order,tuple(assigned)
def plan_capital_quantity(planning_input):
 if type(planning_input)is not CapitalQuantityPlanningInputV1:raise TypeError('planning_input')
 c=resolve_capital_quantity_planning_constraints(planning_input);s=planning_input.option_contract_selection_result
 base=dict(planning_result_id=planning_input.planning_input_id+'-RESULT',planning_input_id=planning_input.planning_input_id,trade_plan_id=planning_input.trade_plan_id,policy_id=planning_input.policy_id,option_selection_result_id=s.selection_result_id,evaluated_at=planning_input.evaluated_at,warnings=planning_input.warnings,source_timestamps=dict(planning_input.source_timestamps),metadata={'effective_constraints':c.to_dict()},execution_mode='PAPER',live_execution_eligible=False)
 if planning_input.blockers or not c.is_coherent:
  return CapitalQuantityPlanningResultV1(status='BLOCKED',blockers=tuple(dict.fromkeys(planning_input.blockers+c.incoherence_codes)),decision_reasons=(),**base)
 common=dict(available_capital=c.available_capital,maximum_capital_utilization_fraction=c.maximum_capital_utilization_fraction,minimum_reserve_capital=c.minimum_reserve_capital,deployable_capital=c.effective_deployable_capital,reserved_capital=c.effective_reserved_capital,risk_model=c.risk_model,maximum_risk_fraction=c.maximum_risk_fraction,maximum_risk_amount=c.maximum_risk_amount,effective_risk_budget=c.effective_risk_budget,per_lot_risk_amount=c.effective_per_lot_risk_amount,risk_based_lot_limit=c.risk_based_lot_limit,estimated_one_lot_premium_cost=c.estimated_one_lot_premium_cost,upstream_affordable_lot_limit=c.upstream_affordable_lot_limit,deployable_capital_affordable_lot_limit=c.deployable_capital_affordable_lot_limit,target_allocation_enabled=False,target_1_lot_count=0,target_2_lot_count=0,target_3_lot_count=0,runner_lot_count=0)
 lots=min(c.upstream_affordable_lot_limit,c.deployable_capital_affordable_lot_limit,c.risk_based_lot_limit,c.effective_maximum_planned_lot_count)
 if lots<c.effective_minimum_planned_lot_count:
  reasons=[]
  if c.upstream_affordable_lot_limit==0 or c.deployable_capital_affordable_lot_limit==0:reasons.append('AFFORDABLE_LOT_LIMIT_ZERO')
  if c.risk_based_lot_limit==0:reasons.append('RISK_LOT_LIMIT_ZERO')
  return CapitalQuantityPlanningResultV1(status='NO_SIZE',blockers=(),decision_reasons=tuple(reasons or ['NO_PERMISSIBLE_QUANTITY']),planned_lot_count=0,lot_size=c.estimated_one_lot_premium_cost and s.selected_lot_size,planned_quantity=0,estimated_premium_outlay=0.,estimated_risk_amount=0.,**common,**base)
 q=lots*s.selected_lot_size
 evidence=planning_input.trading_cost_evidence
 if evidence is not None and (evidence.planned_lot_count!=lots or evidence.lot_size!=s.selected_lot_size or evidence.planned_quantity!=q or evidence.estimated_order_count!=planning_input.trading_cost_policy.estimated_order_count or abs(evidence.estimated_premium_outlay-lots*c.estimated_one_lot_premium_cost)>1e-9):
  return CapitalQuantityPlanningResultV1(status='BLOCKED',blockers=('TRADING_COST_EVIDENCE_MISMATCH',),decision_reasons=(),**base)
 if evidence is not None and evidence.estimated_total_capital_requirement>c.effective_deployable_capital:
  return CapitalQuantityPlanningResultV1(status='NO_SIZE',blockers=(),decision_reasons=('TRADING_COST_CAPITAL_INSUFFICIENT',),planned_lot_count=0,lot_size=s.selected_lot_size,planned_quantity=0,estimated_premium_outlay=0.,estimated_risk_amount=0.,**common,**base)
 if planning_input.capital_quantity_policy.target_allocation_enabled:
  weights=planning_input.capital_quantity_policy.target_allocation_weights;allocated,exact,fractions,order,assigned=_allocate_target_lots(lots,weights)
  common.update(target_allocation_enabled=True,target_1_lot_count=allocated[0],target_2_lot_count=allocated[1],target_3_lot_count=allocated[2],runner_lot_count=0)
  base['metadata']=dict(base['metadata'],target_allocation={'enabled':True,'weights':weights,'remainder_priority':('T1','T2','T3'),'exact_shares':exact,'base_counts':tuple(int(x) for x in exact),'fractional_remainders':fractions,'remainder_assignment_order':tuple(('T1','T2','T3')[i] for i in assigned),'final_counts':allocated,'allocation_total':sum(allocated),'runner_lot_count':0})
 return CapitalQuantityPlanningResultV1(status='READY',blockers=(),decision_reasons=(),planned_lot_count=lots,lot_size=s.selected_lot_size,planned_quantity=q,estimated_premium_outlay=lots*c.estimated_one_lot_premium_cost,estimated_risk_amount=lots*c.effective_per_lot_risk_amount,**common,**base)
