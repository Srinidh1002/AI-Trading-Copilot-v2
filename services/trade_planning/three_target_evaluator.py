from services.contracts.three_target_evaluation_input_v1 import ThreeTargetEvaluationInputV1
from services.contracts.three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from services.contracts.trade_plan_target_v1 import TradePlanTargetV1
from services.contracts.trade_planning_policy_v1 import TradePlanningPolicyV1
def evaluate_three_targets(evaluation_input,policy):
 if type(evaluation_input)is not ThreeTargetEvaluationInputV1 or type(policy)is not TradePlanningPolicyV1:raise TypeError('exact typed inputs required')
 blockers=evaluation_input.blockers
 if not evaluation_input.planning_allowed:blockers+=('TARGET_PLANNING_NOT_ALLOWED',)
 if evaluation_input.policy_id!=policy.policy_id:blockers+=('TARGET_POLICY_MISMATCH',)
 def out(status,targets=(None,None,None),source=None,bs=(),warnings=()):return ThreeTargetEvaluationResultV1(evaluation_result_id=evaluation_input.evaluation_result_id,evaluation_id=evaluation_input.evaluation_id,evaluated_at=evaluation_input.evaluated_at,underlying_symbol=evaluation_input.underlying_symbol,exchange=evaluation_input.exchange,direction=evaluation_input.direction,option_right=evaluation_input.option_right,target_method=policy.target_method,selected_target_source=source,status=status,target_1=targets[0],target_2=targets[1],target_3=targets[2],entry_reference_price=evaluation_input.entry_reference_price,stop_loss_price=evaluation_input.stop_loss_price,stop_distance=evaluation_input.stop_distance,stop_distance_fraction=evaluation_input.stop_distance_fraction,minimum_reward_to_risk_t1=policy.minimum_reward_to_risk_t1,minimum_reward_to_risk_t2=policy.minimum_reward_to_risk_t2,minimum_reward_to_risk_t3=policy.minimum_reward_to_risk_t3,target_1_multiplier=policy.target_1_multiplier,target_2_multiplier=policy.target_2_multiplier,target_3_multiplier=policy.target_3_multiplier,blockers=tuple(dict.fromkeys(bs)),warnings=warnings,source_timestamps=dict(evaluation_input.source_timestamps),metadata={'entry_evaluation_result_id':evaluation_input.entry_evaluation_result_id,'stop_evaluation_result_id':evaluation_input.stop_evaluation_result_id,'policy_id':policy.policy_id})
 if blockers:return out('BLOCKED',bs=blockers)
 mult=(policy.target_1_multiplier,policy.target_2_multiplier,policy.target_3_multiplier)
 def build(vals,source):
  if not all(x>evaluation_input.entry_reference_price for x in vals) or not vals[0]<vals[1]<vals[2]:return None
  ts=tuple(TradePlanTargetV1(i,v,a,v-evaluation_input.entry_reference_price,(v-evaluation_input.entry_reference_price)/evaluation_input.stop_distance,r) for i,v,a,r in zip((1,2,3),vals,(policy.target_1_allocation_fraction,policy.target_2_allocation_fraction,policy.target_3_allocation_fraction),('RISK_REDUCTION','PRIMARY','EXTENDED')))
  if any(t.reward_to_risk<m for t,m in zip(ts,(policy.minimum_reward_to_risk_t1,policy.minimum_reward_to_risk_t2,policy.minimum_reward_to_risk_t3))):return 'rr'
  return ts
 def candidate(method):
  if method=='RISK_MULTIPLE':return build(tuple(evaluation_input.entry_reference_price+evaluation_input.stop_distance*x for x in mult),'RISK_MULTIPLE')
  v=evaluation_input.atr_value if method=='ATR' else evaluation_input.expected_move_value if method=='EXPECTED_MOVE' else None
  if method in {'ATR','EXPECTED_MOVE'}:return None if v is None else build(tuple(evaluation_input.entry_reference_price+v*x for x in mult),method)
  explicit=(evaluation_input.structure_target_1,evaluation_input.structure_target_2,evaluation_input.structure_target_3)
  if any(x is not None for x in explicit) and any(x is None for x in explicit):return 'partial'
  return build(explicit,'STRUCTURE') if all(explicit) else build(tuple(sorted(x for x in evaluation_input.resistance_levels if x>evaluation_input.entry_reference_price)[:3]),'RESISTANCE_LEVELS') if len([x for x in evaluation_input.resistance_levels if x>evaluation_input.entry_reference_price])>=3 else None
 methods=[policy.target_method] if policy.target_method!='HYBRID' else ['STRUCTURE','EXPECTED_MOVE','ATR','RISK_MULTIPLE']
 valid=[];reasons=[]
 for m in methods:
  c=candidate(m)
  if isinstance(c,tuple):valid.append((m,c))
  else:reasons.append(c)
 if not valid:return out('BLOCKED',bs=('TARGET_STRUCTURE_INCOMPLETE' if 'partial' in reasons else 'TARGET_REWARD_TO_RISK_BELOW_MINIMUM' if 'rr' in reasons else 'TARGET_REFERENCE_UNAVAILABLE',))
 m,ts=max(valid,key=lambda x:(x[1][1].reward_to_risk,-['STRUCTURE','EXPECTED_MOVE','ATR','RISK_MULTIPLE'].index(x[0])))
 source='STRUCTURE_EXPLICIT' if m=='STRUCTURE' and all((evaluation_input.structure_target_1,evaluation_input.structure_target_2,evaluation_input.structure_target_3)) else 'RESISTANCE_LEVELS' if m=='STRUCTURE' else m
 return out('READY',ts,source,warnings=evaluation_input.warnings+(('TARGET_HYBRID_FALLBACK_USED',) if policy.target_method=='HYBRID' and m!='STRUCTURE' else ()))
