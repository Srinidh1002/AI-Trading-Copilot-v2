"""Pure deterministic first-valid selector over already-ranked P5 candidates."""
from __future__ import annotations
import math
from services.contracts.option_contract_selection_input_v1 import OptionContractSelectionInputV1
from services.contracts.option_contract_selection_result_v1 import OptionContractSelectionResultV1
from services.contracts.trade_planning_policy_v1 import TradePlanningPolicyV1
from services.trade_planning.option_contract_selection_constraints import resolve_option_contract_selection_constraints
def select_option_contract(selection_input,policy):
 if type(selection_input)is not OptionContractSelectionInputV1:raise TypeError('selection_input must be OptionContractSelectionInputV1')
 if type(policy)is not TradePlanningPolicyV1:raise TypeError('policy must be TradePlanningPolicyV1')
 early=selection_input.blockers
 if not selection_input.planning_allowed:early+=('CONTRACT_PLANNING_NOT_ALLOWED',)
 if not selection_input.session_allows_new_entries:early+=('CONTRACT_SESSION_BLOCKED',)
 if selection_input.event_restriction_active:early+=('CONTRACT_EVENT_BLOCKED',)
 constraints=resolve_option_contract_selection_constraints(selection_input,policy)
 cap=constraints.effective_maximum_entry_premium;spread=constraints.effective_maximum_spread_fraction
 if not constraints.is_coherent:early+=('CONTRACT_POLICY_MISMATCH',)
 ranking=selection_input.option_ranking_result
 if ranking.ranking_status not in {'RANKED','RANKED_WITH_WARNINGS'} or not ranking.ranked_candidates:early+=('CONTRACT_RANKING_UNAVAILABLE',)
 def out(status,c=None,rank=None,reasons=(),warnings=(),e={},cost=None,lots=None,evaluations=()):
  flags=dict(premium_affordable=None,spread_acceptable=None,liquidity_acceptable=None,open_interest_acceptable=None,volume_acceptable=None,moneyness_acceptable=None,expiry_acceptable=None,lot_size_acceptable=None,session_acceptable=selection_input.session_allows_new_entries,event_acceptable=not selection_input.event_restriction_active);flags.update(e)
  return OptionContractSelectionResultV1(selection_result_id=selection_input.selection_result_id,selection_id=selection_input.selection_id,evaluated_at=selection_input.evaluated_at,underlying_symbol=selection_input.underlying_symbol,exchange=selection_input.exchange,direction=selection_input.direction,option_right=selection_input.option_right,status=status,selected_contract=c,selected_rank=rank,selected_score=c.total_score if c else None,selected_reason_codes=c.rejection_reasons if c else (),effective_maximum_entry_premium=cap,effective_maximum_spread_fraction=spread,estimated_one_lot_premium_cost=cost,affordable_lot_count=lots,blockers=tuple(dict.fromkeys(reasons)) if status=='BLOCKED' else (),warnings=tuple(dict.fromkeys(warnings)),decision_reasons=tuple(dict.fromkeys(reasons)) if status=='NO_CONTRACT' else (),source_timestamps=dict(selection_input.source_timestamps),metadata={'option_ranking_result_id':ranking.ranking_id,'policy_id':policy.policy_id,'effective_maximum_entry_premium':cap,'effective_maximum_spread_fraction':spread,'effective_constraints':constraints.to_dict(),'candidate_evaluations':evaluations,'policy_incoherence_codes':list(constraints.incoherence_codes),'selected_candidate_id':c.contract.contract_id if c else None,'selected_candidate_rank':rank,'selected_raw_affordable_lot_count':next((v['raw_affordable_lot_count'] for v in evaluations if c and v['candidate_id']==c.contract.contract_id),None),'selected_capped_affordable_lot_count':lots,'selector_stage':'POLICY_COHERENCE' if not constraints.is_coherent else 'CANDIDATE_SELECTION'},**flags)
 if early:return out('BLOCKED',reasons=early)
 rejected=[];evaluations=[]
 for rank,c in enumerate(ranking.ranked_candidates,1):
  x=c.contract;rs=[]
  if (x.underlying_symbol,x.exchange)!=(selection_input.underlying_symbol,selection_input.exchange):rs+=['CONTRACT_IDENTITY_MISMATCH']
  if x.option_type!=selection_input.option_right:rs+=['CONTRACT_RIGHT_MISMATCH']
  p=x.last_price
  if type(p)not in (int,float) or isinstance(p,bool) or not math.isfinite(p) or p<=0:rs+=['CONTRACT_PREMIUM_INVALID']
  elif cap is not None and p>cap:rs+=['CONTRACT_PREMIUM_LIMIT_EXCEEDED']
  sf=c.spread_percent/100 if c.spread_percent is not None else None
  if spread is not None and sf is None:rs+=['CONTRACT_SPREAD_UNAVAILABLE']
  elif spread is not None and sf>spread:rs+=['CONTRACT_SPREAD_LIMIT_EXCEEDED']
  if c.moneyness not in constraints.effective_allowed_moneyness:rs+=['CONTRACT_MONEYNESS_BLOCKED']
  evidence=selection_input.get_candidate_eligibility_evidence(x.contract_id)
  if evidence is None:rs+=['CONTRACT_ELIGIBILITY_EVIDENCE_UNAVAILABLE']
  else:
   if evidence.moneyness_steps>constraints.effective_maximum_moneyness_steps:rs+=['CONTRACT_MONEYNESS_BLOCKED']
   if evidence.expiry_category=='WEEKLY' and not constraints.effective_allow_weekly_expiry:rs+=['CONTRACT_EXPIRY_BLOCKED']
   if evidence.expiry_category=='MONTHLY' and not constraints.effective_allow_monthly_expiry:rs+=['CONTRACT_EXPIRY_BLOCKED']
   if evidence.days_to_expiry==0 and not constraints.effective_allow_same_day_expiry:rs+=['CONTRACT_SAME_DAY_EXPIRY_BLOCKED']
   if evidence.days_to_expiry<constraints.effective_minimum_days_to_expiry or (constraints.effective_maximum_days_to_expiry is not None and evidence.days_to_expiry>constraints.effective_maximum_days_to_expiry):rs+=['CONTRACT_EXPIRY_BLOCKED']
  if x.open_interest is None or x.open_interest<constraints.effective_minimum_open_interest:rs+=['CONTRACT_OPEN_INTEREST_LOW']
  if x.volume is None or x.volume<constraints.effective_minimum_volume:rs+=['CONTRACT_VOLUME_LOW']
  if constraints.effective_minimum_liquidity_score is not None and (type(c.liquidity_score)not in (int,float) or isinstance(c.liquidity_score,bool) or not math.isfinite(c.liquidity_score)):rs+=['CONTRACT_LIQUIDITY_UNAVAILABLE']
  elif constraints.effective_minimum_liquidity_score is not None and c.liquidity_score<constraints.effective_minimum_liquidity_score:rs+=['CONTRACT_LIQUIDITY_LOW']
  if type(x.lot_size)is not int or isinstance(x.lot_size,bool) or x.lot_size<=0:rs+=['CONTRACT_LOT_LIMIT_BLOCKED'];cost=None;raw_lots=None;lots=None
  else:
   cost=p*x.lot_size if type(p) in (int,float) and not isinstance(p,bool) and math.isfinite(p) and p>0 else None
   raw_lots=math.floor(selection_input.available_capital/cost) if cost else 0
   lots=min(raw_lots,constraints.effective_maximum_lot_count)
   if cost is None:rs+=['CONTRACT_LOT_LIMIT_BLOCKED']
   elif raw_lots<constraints.effective_minimum_lot_count:rs+=['CONTRACT_UNAFFORDABLE']
  evaluation={'candidate_id':x.contract_id,'rank':rank,'evidence_id':evidence.evidence_id if evidence else None,'evidence_source':evidence.evidence_source if evidence else None,'moneyness_steps':evidence.moneyness_steps if evidence else None,'expiry_category':evidence.expiry_category if evidence else None,'days_to_expiry':evidence.days_to_expiry if evidence else None,'premium':p,'lot_size':x.lot_size,'one_lot_premium_cost':cost,'raw_affordable_lot_count':raw_lots,'capped_affordable_lot_count':lots,'rejection_codes':tuple(rs)}
  evaluations.append(evaluation)
  if rs:rejected+=rs;continue
  e=dict(premium_affordable=True,spread_acceptable=True if sf is not None else None,liquidity_acceptable=True,open_interest_acceptable=True,volume_acceptable=True,moneyness_acceptable=True,expiry_acceptable=True,lot_size_acceptable=True,session_acceptable=True,event_acceptable=True)
  # READY requires a spread truth value; lack of a limit is not a failure.
  e['spread_acceptable']=True
  return out('READY',c,rank,warnings=selection_input.warnings+(('CONTRACT_RANKED_FALLBACK_USED',) if rank>1 else ()),e=e,cost=cost,lots=lots,evaluations=tuple(evaluations))
 return out('NO_CONTRACT',reasons=rejected or ('CONTRACT_RANKING_UNAVAILABLE',),warnings=selection_input.warnings,evaluations=tuple(evaluations))
