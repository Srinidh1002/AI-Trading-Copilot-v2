"""Pure PAPER entry transition evaluation; no runtime or persistence dependencies."""
from __future__ import annotations
from dataclasses import replace
from datetime import date
from services.contracts.paper_trade_entry_evaluation_input_v1 import PaperTradeEntryEvaluationInputV1
from services.contracts.paper_trade_entry_evaluation_result_v1 import PaperTradeEntryEvaluationResultV1
from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.paper_trade_position_v1 import PaperTradePositionV1
from services.contracts.paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1

def _result(i,status,decision,state,*,price,lower,upper,fill=None,position=None,blockers=(),reasons=(),warnings=(),fresh=True,order=True,session=True,expiry=True):
 return PaperTradeEntryEvaluationResultV1(i.requested_transition_id,i.requested_transition_id,i.observation.trade_plan_id,i.integrated_trade_plan_result.integration_id,i.lifecycle_policy.lifecycle_policy_id,i.lifecycle_state.lifecycle_state_id,i.observation.observation_id,status,decision,state,'SELECTED_OPTION_PREMIUM',price,lower,upper,i.integrated_trade_plan_result.entry_zone_result.entry_reference_price,status=='OPEN',i.observation.observed_at,fresh,order,session,expiry,position,fill,blockers,reasons,warnings,{'source_lifecycle_state':i.lifecycle_state.current_state,'entry_price_basis':'SELECTED_OPTION_PREMIUM','original_entry_zone_lower':i.integrated_trade_plan_result.entry_zone_result.entry_zone_lower,'original_entry_zone_upper':i.integrated_trade_plan_result.entry_zone_result.entry_zone_upper})
def evaluate_paper_trade_entry(evaluation_input:PaperTradeEntryEvaluationInputV1)->PaperTradeEntryEvaluationResultV1:
 if type(evaluation_input)is not PaperTradeEntryEvaluationInputV1:raise TypeError('evaluation_input')
 i=evaluation_input;o=i.observation;p=i.lifecycle_policy;s=i.lifecycle_state;e=i.integrated_trade_plan_result.entry_zone_result
 price=o.option_last_price;tolerance=e.entry_reference_price*p.entry_zone_tolerance_fraction;lower=e.entry_zone_lower-tolerance;upper=e.entry_zone_upper+tolerance
 if o.observed_at>i.evaluation_timestamp:return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('OBSERVATION_FROM_FUTURE',),fresh=False,order=False,session=False,expiry=False)
 if p.reject_duplicate_observation and o.observation_id==s.last_observation_id:return _result(i,'WAITING_FOR_ENTRY','WAIT',s.current_state,price=price,lower=lower,upper=upper,reasons=('DUPLICATE_OBSERVATION_IGNORED',),order=False)
 if p.reject_out_of_order_observation and s.last_observation_timestamp and o.observed_at<s.last_observation_timestamp:return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('OUT_OF_ORDER_OBSERVATION',),order=False)
 age=(i.evaluation_timestamp-o.observed_at).total_seconds()
 if p.require_fresh_observation and age>p.maximum_observation_age_seconds:return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('STALE_OBSERVATION',),fresh=False)
 if o.data_quality_status in {'INVALID','STALE'}:return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('INVALID_DATA_QUALITY',))
 if o.session_state=='UNKNOWN':return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('INVALID_SESSION_STATE',),session=False)
 if o.session_state!='OPEN':
  if p.close_at_session_end:return _result(i,'CLOSED_SESSION','SESSION_CLOSE','CLOSED_SESSION',price=price,lower=lower,upper=upper,reasons=('ENTRY_SESSION_ENDED',),session=False)
  return _result(i,'WAITING_FOR_ENTRY','WAIT',s.current_state,price=price,lower=lower,upper=upper,reasons=('WAITING_FOR_ENTRY_ZONE',),session=False)
 expiry_value=i.integrated_trade_plan_result.option_contract_selection_result.selected_contract.contract.expiry_date
 expiry=date.fromisoformat(expiry_value) if type(expiry_value) is str else expiry_value
 if i.evaluation_timestamp.date()>=expiry:
  if p.close_at_expiry:return _result(i,'CLOSED_EXPIRY','EXPIRY_CLOSE','CLOSED_EXPIRY',price=price,lower=lower,upper=upper,reasons=('ENTRY_EXPIRY_REACHED',),expiry=False)
  return _result(i,'WAITING_FOR_ENTRY','WAIT',s.current_state,price=price,lower=lower,upper=upper,reasons=('WAITING_FOR_ENTRY_ZONE',),expiry=False)
 start=s.waiting_for_entry_at or s.lifecycle_created_at
 if (i.evaluation_timestamp-start).total_seconds()>p.entry_timeout_seconds:return _result(i,'CLOSED_INVALIDATED','INVALIDATE','CLOSED_INVALIDATED',price=price,lower=lower,upper=upper,reasons=('ENTRY_TIMEOUT',))
 lo=o.option_low if o.option_low is not None else price;hi=o.option_high if o.option_high is not None else price
 if p.entry_activation_mode=='ZONE_CLOSE':
  if o.option_close is None:return _result(i,'BLOCKED','BLOCK','BLOCKED',price=price,lower=lower,upper=upper,blockers=('ENTRY_PRICE_EVIDENCE_UNAVAILABLE',))
  touched=lower<=o.option_close<=upper;fill_price=o.option_close
 elif p.entry_activation_mode=='PREFERRED_ENTRY_TOUCH':
  preferred=e.entry_reference_price; touched=lo<=preferred<=hi;fill_price=preferred
 else:touched=lo<=upper and hi>=lower;fill_price=min(upper,hi)
 gap_up=o.option_open is not None and o.option_open>upper and lo>upper
 gap_down=o.option_open is not None and o.option_open<lower and hi<lower
 if p.entry_activation_mode!='ZONE_CLOSE' and (gap_up or gap_down):
  if gap_up and p.allow_gap_entry:
   touched=True;fill_price=o.option_open
  elif gap_down:
   touched=False
  elif not p.allow_gap_entry:touched=False
 if not touched:return _result(i,'WAITING_FOR_ENTRY','WAIT',s.current_state,price=price,lower=lower,upper=upper,reasons=('WAITING_FOR_ENTRY_ZONE',))
 cap=i.integrated_trade_plan_result.capital_quantity_result;sel=i.integrated_trade_plan_result.option_contract_selection_result.selected_contract.contract
 warnings=(() if abs(fill_price-sel.last_price)<1e-9 else ('ENTRY_PRICE_DIFFERS_FROM_P6_PREMIUM',))+(('GAP_ENTRY_ACTIVATED',) if gap_up and p.allow_gap_entry else ())
 fill=PaperTradeFillV1(i.entry_fill_id,o.trade_plan_id,i.integrated_trade_plan_result.integration_id,i.position_id,o.observation_id,sel.contract_id,'ENTRY','ENTRY_ACTIVATED','BUY',cap.planned_lot_count,cap.lot_size,cap.planned_quantity,fill_price,cap.planned_quantity*fill_price,0.,-(cap.planned_quantity*fill_price),i.evaluation_timestamp,'P7_WP2')
 targets=i.integrated_trade_plan_result.three_target_result
 direction='BULLISH' if sel.option_type=='CALL' else 'BEARISH'
 position=PaperTradePositionV1(i.position_id,o.trade_plan_id,i.integrated_trade_plan_result.integration_id,p.lifecycle_policy_id,s.lifecycle_state_id,sel.contract_id,o.market,o.underlying_symbol,o.option_symbol,direction,sel.option_type,sel.strike,sel.expiry_date.isoformat() if hasattr(sel.expiry_date,'isoformat') else sel.expiry_date,fill,fill_price,i.evaluation_timestamp,cap.planned_lot_count,cap.lot_size,cap.planned_quantity,cap.planned_lot_count,cap.planned_quantity,cap.target_1_lot_count or 0,cap.target_2_lot_count or 0,cap.target_3_lot_count or 0,cap.runner_lot_count or 0,i.integrated_trade_plan_result.stop_loss_result.stop_loss_price,targets.target_1.target_price,targets.target_2.target_price,targets.target_3.target_price,cap.estimated_premium_outlay,cap.estimated_risk_amount,cap.estimated_total_trading_cost or 0.,cap.estimated_total_capital_requirement or cap.estimated_premium_outlay,exchange=sel.exchange)
 return _result(i,'OPEN','ACTIVATE','OPEN',price=price,lower=lower,upper=upper,fill=fill,position=position,reasons=('ENTRY_ACTIVATED',),warnings=warnings)
