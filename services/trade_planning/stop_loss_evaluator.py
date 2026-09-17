"""Pure deterministic, PAPER-only option-premium stop-loss evaluation."""
from __future__ import annotations
from typing import Any
from services.contracts.canonical_trade_plan_input_v1 import CanonicalTradePlanInputV1
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.stop_loss_evaluation_input_v1 import StopLossEvaluationInputV1
from services.contracts.stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from services.contracts.trade_planning_policy_v1 import TradePlanningPolicyV1

_PRIORITY={"STRUCTURE_STOP":0,"RECENT_SWING_LOW":0,"ATR":1,"PREMIUM_FRACTION":2}
_TOLERANCE=1e-9
def _dedupe(values):return tuple(dict.fromkeys(values))

def evaluate_stop_loss(trade_plan_input:CanonicalTradePlanInputV1, policy:TradePlanningPolicyV1, entry_result:EntryZoneEvaluationResultV1, stop_input:StopLossEvaluationInputV1)->StopLossEvaluationResultV1:
 """Evaluate supplied option-premium evidence; never fetches or executes anything."""
 if type(trade_plan_input)is not CanonicalTradePlanInputV1:raise TypeError("trade_plan_input must be CanonicalTradePlanInputV1")
 if type(policy)is not TradePlanningPolicyV1:raise TypeError("policy must be TradePlanningPolicyV1")
 if type(entry_result)is not EntryZoneEvaluationResultV1:raise TypeError("entry_result must be EntryZoneEvaluationResultV1")
 if type(stop_input)is not StopLossEvaluationInputV1:raise TypeError("stop_input must be StopLossEvaluationInputV1")
 early=stop_input.blockers
 if not stop_input.planning_allowed or not trade_plan_input.planning_allowed:early+=("STOP_PLANNING_NOT_ALLOWED",)
 coherence=(stop_input.policy_id!=policy.policy_id or stop_input.trade_plan_input_id!=trade_plan_input.trade_plan_input_id or stop_input.entry_evaluation_result_id!=entry_result.evaluation_result_id or (stop_input.underlying_symbol,stop_input.exchange)!=(trade_plan_input.underlying_symbol,trade_plan_input.exchange) or (stop_input.underlying_symbol,stop_input.exchange)!=(entry_result.underlying_symbol,entry_result.exchange) or stop_input.direction!=entry_result.direction or stop_input.option_right!=entry_result.option_right or any(x.execution_mode!="PAPER" or x.live_execution_eligible is not False for x in (trade_plan_input,policy,entry_result,stop_input)))
 if coherence:early+=("STOP_POLICY_MISMATCH",)
 entry_ok=(entry_result.status=="READY" and entry_result.entry_reference_price==stop_input.entry_reference_price and entry_result.entry_zone_lower==stop_input.entry_zone_lower and entry_result.entry_zone_upper==stop_input.entry_zone_upper)
 if not entry_ok:early+=("STOP_ENTRY_EVIDENCE_INVALID",)
 def result(status,source=None,stop=None,blockers=(),warnings=stop_input.warnings,candidates=None):
  distance=None if stop is None else stop_input.entry_reference_price-stop
  fraction=None if distance is None else distance/stop_input.entry_reference_price
  geometry=stop is not None
  return StopLossEvaluationResultV1(evaluation_result_id=stop_input.evaluation_result_id,evaluation_id=stop_input.evaluation_id,evaluated_at=stop_input.evaluated_at,underlying_symbol=stop_input.underlying_symbol,exchange=stop_input.exchange,direction=stop_input.direction,option_right=stop_input.option_right,stop_method=policy.stop_loss_method,selected_stop_source=source,status=status,stop_loss_price=stop,stop_reference_price=stop_input.entry_reference_price if geometry else None,stop_distance=distance,stop_distance_fraction=fraction,minimum_stop_distance_fraction=policy.minimum_stop_distance_fraction if geometry else None,maximum_stop_distance_fraction=policy.maximum_stop_distance_fraction if geometry else None,blockers=_dedupe(blockers),warnings=_dedupe(warnings),decision_reasons=(),invalidation_rules=("STOP_OPTION_PREMIUM_BREACH",) if status=="READY" else (),source_timestamps=dict(stop_input.source_timestamps),metadata={"input_metadata":stop_input.to_dict()["metadata"],"entry_evaluation_result_id":stop_input.entry_evaluation_result_id,"policy_id":policy.policy_id,"selected_stop_source":source,"candidate_stop_values":candidates or {},"comparison_tolerance":_TOLERANCE},execution_mode="PAPER",live_execution_eligible=False,schema_version="1.0")
 if early:return result("BLOCKED",blockers=early)
 def valid(source,stop):
  if stop is None:return None,"missing"
  if stop<=0 or stop>=stop_input.entry_reference_price:return None,"price"
  f=(stop_input.entry_reference_price-stop)/stop_input.entry_reference_price
  if not policy.minimum_stop_distance_fraction-_TOLERANCE<=f<=policy.maximum_stop_distance_fraction+_TOLERANCE:return None,"distance"
  return stop,None
 def atr():
  if stop_input.atr_value is None or policy.stop_loss_atr_multiplier is None:return None,"missing"
  return valid("ATR",stop_input.entry_reference_price-stop_input.atr_value*policy.stop_loss_atr_multiplier)
 def structure():
  if stop_input.structure_stop_price is not None:raw,source=stop_input.structure_stop_price,"STRUCTURE_STOP"
  elif stop_input.recent_swing_low is not None:raw,source=stop_input.recent_swing_low,"RECENT_SWING_LOW"
  else:return None,"missing"
  return valid(source,raw*(1-policy.stop_loss_structure_buffer_fraction))
 def premium():
  if policy.stop_loss_premium_fraction is None:return None,"missing"
  if stop_input.premium_reference_price is not None and abs(stop_input.premium_reference_price-stop_input.entry_reference_price)>_TOLERANCE*stop_input.entry_reference_price:return None,"entry"
  return valid("PREMIUM_FRACTION",stop_input.entry_reference_price*(1-policy.stop_loss_premium_fraction))
 methods={"ATR":atr,"STRUCTURE":structure,"PREMIUM_FRACTION":premium}
 if policy.stop_loss_method!="HYBRID":
  stop,reason=methods[policy.stop_loss_method]()
  source={"ATR":"ATR","STRUCTURE":"STRUCTURE_STOP" if stop_input.structure_stop_price is not None else "RECENT_SWING_LOW","PREMIUM_FRACTION":"PREMIUM_FRACTION"}[policy.stop_loss_method] if stop else None
  if stop:return result("READY",source,stop)
  code={"missing":"STOP_REFERENCE_UNAVAILABLE","price":"STOP_PRICE_INVALID","distance":"STOP_DISTANCE_OUT_OF_RANGE","entry":"STOP_ENTRY_EVIDENCE_INVALID"}[reason]
  return result("BLOCKED",blockers=(code,))
 candidates={}; reasons=[]
 for method,fn in methods.items():
  stop,reason=fn()
  if stop is not None:
   src="ATR" if method=="ATR" else "PREMIUM_FRACTION" if method=="PREMIUM_FRACTION" else "STRUCTURE_STOP" if stop_input.structure_stop_price is not None else "RECENT_SWING_LOW"
   candidates[src]=stop
  else:reasons.append(reason)
 if not candidates:
  code="STOP_REFERENCE_UNAVAILABLE" if all(x=="missing" for x in reasons) else "STOP_POLICY_CONSTRAINT_FAILED"
  return result("BLOCKED",blockers=(code,),candidates=candidates)
 source,stop=sorted(candidates.items(),key=lambda x:(-x[1],_PRIORITY[x[0]],x[0]))[0]
 warnings=stop_input.warnings + (("STOP_HYBRID_FALLBACK_USED",) if source not in {"STRUCTURE_STOP","RECENT_SWING_LOW"} else ())
 return result("READY",source,stop,warnings=warnings,candidates=candidates)
