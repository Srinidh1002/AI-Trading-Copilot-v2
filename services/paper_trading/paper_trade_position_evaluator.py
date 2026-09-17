"""Pure deterministic PAPER open-position evaluator."""
from __future__ import annotations
from dataclasses import replace
from datetime import date
from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.paper_trade_pnl_evidence_v1 import PaperTradePnlEvidenceV1
from services.contracts.paper_trade_position_evaluation_input_v1 import PaperTradePositionEvaluationInputV1
from services.contracts.paper_trade_position_evaluation_result_v1 import PaperTradePositionEvaluationResultV1
from services.contracts.paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1

def _lifecycle(i,name,reason):
 s=i.lifecycle_state
 if name==s.current_state:return s
 values=dict(lifecycle_state_id=i.resulting_lifecycle_state_id,trade_plan_id=s.trade_plan_id,integrated_trade_plan_result_id=s.integrated_trade_plan_result_id,lifecycle_policy_id=s.lifecycle_policy_id,current_state=name,lifecycle_created_at=s.lifecycle_created_at,previous_state=s.current_state,transition_sequence=s.transition_sequence+1,last_transition_code=i.requested_transition_id,last_observation_id=i.observation.observation_id,last_observation_timestamp=i.observation.observed_at,metadata={'transition_reason':reason})
 if name=='PARTIALLY_EXITED':values['partially_exited_at']=i.evaluation_timestamp
 if name.startswith('CLOSED_'):
  values.update(closed_at=i.evaluation_timestamp,terminal_reason=reason,is_terminal=True)
  if name in {'CLOSED_TARGET_1','CLOSED_TARGET_2','CLOSED_TARGET_3'}:values['terminal_target']='T'+name[-1]
 if name=='CANCELLED':values.update(cancelled_at=i.evaluation_timestamp,terminal_reason=reason,is_terminal=True)
 return PaperTradeLifecycleStateV1(**values)

def _hit(o,price,mode,*,stop=False):
 if mode=='CLOSE': return o.option_close is not None and (o.option_close<=price if stop else o.option_close>=price)
 lo=o.option_low if o.option_low is not None else o.option_last_price; hi=o.option_high if o.option_high is not None else o.option_last_price
 return lo<=price<=hi or (o.option_last_price<=price if stop else o.option_last_price>=price)
def _exit(i,fill_id,lots,price,reason,cost,target=None):
 p=i.position;q=lots*p.lot_size;gross=q*price
 return PaperTradeFillV1(fill_id,p.trade_plan_id,p.integrated_trade_plan_result_id,p.position_id,i.observation.observation_id,p.selected_option_contract_id,'EXIT',reason,'SELL',lots,p.lot_size,q,price,gross,cost,gross-cost,i.evaluation_timestamp,'P7_WP3',target)
def evaluate_open_paper_trade_position(i:PaperTradePositionEvaluationInputV1)->PaperTradePositionEvaluationResultV1:
 if type(i)is not PaperTradePositionEvaluationInputV1:raise TypeError('evaluation_input')
 p,o,policy,state=i.position,i.observation,i.lifecycle_policy,i.lifecycle_state
 base=dict(evaluation_result_id=i.evaluation_result_id,requested_transition_id=i.requested_transition_id,source_position_id=p.position_id,source_lifecycle_state_id=state.lifecycle_state_id,observation_id=o.observation_id,evaluated_option_price=o.option_last_price)
 if o.observed_at>i.evaluation_timestamp:return PaperTradePositionEvaluationResultV1(**base,status='BLOCKED',position_decision='BLOCK',resulting_position=None,resulting_lifecycle_state=state,generated_exit_fills=(),pnl_evidence=None,observation_fresh=False,observation_order_valid=False,blockers=('OBSERVATION_FROM_FUTURE',))
 if policy.reject_duplicate_observation and o.observation_id==state.last_observation_id:
  return _hold(i,base,reason='DUPLICATE_OBSERVATION_IGNORED',order=False,economic_noop=True)
 if policy.reject_out_of_order_observation and state.last_observation_timestamp and o.observed_at<state.last_observation_timestamp:return PaperTradePositionEvaluationResultV1(**base,status='BLOCKED',position_decision='BLOCK',resulting_position=None,resulting_lifecycle_state=state,generated_exit_fills=(),pnl_evidence=None,observation_order_valid=False,blockers=('OUT_OF_ORDER_OBSERVATION',))
 if policy.require_fresh_observation and (i.evaluation_timestamp-o.observed_at).total_seconds()>policy.maximum_observation_age_seconds:return PaperTradePositionEvaluationResultV1(**base,status='BLOCKED',position_decision='BLOCK',resulting_position=None,resulting_lifecycle_state=state,generated_exit_fills=(),pnl_evidence=None,observation_fresh=False,blockers=('STALE_OBSERVATION',))
 if o.data_quality_status in {'STALE','INVALID'}:return PaperTradePositionEvaluationResultV1(**base,status='BLOCKED',position_decision='BLOCK',resulting_position=None,resulting_lifecycle_state=state,generated_exit_fills=(),pnl_evidence=None,blockers=('INVALID_DATA_QUALITY',))
 expiry=date.fromisoformat(p.expiry) if type(p.expiry)is str else p.expiry
 reason=cost=None
 if i.evaluation_timestamp.date()>=expiry and policy.close_at_expiry:reason,cost='EXPIRY_CLOSE',i.expiry_exit_cost
 elif o.session_state!='OPEN' and policy.close_at_session_end:reason,cost='SESSION_CLOSE',i.session_exit_cost
 elif i.cancellation_status=='REQUESTED':reason,cost='CANCELLED',i.cancellation_exit_cost
 elif i.invalidation_status=='TRIGGERED':reason,cost='INVALIDATION',i.invalidation_exit_cost
 stop=_hit(o,p.stop_loss,policy.stop_trigger_mode,stop=True); targets=[_hit(o,x,policy.target_trigger_mode) for x in (p.target_1,p.target_2,p.target_3)]
 if reason is None and stop and (policy.same_observation_precedence!='TARGET_FIRST' or not any(targets)):reason,cost='STOP',i.stop_exit_cost
 fills=[]
 if reason:
  price=o.option_close if (reason in {'SESSION_CLOSE','EXPIRY_CLOSE'} or policy.stop_trigger_mode=='CLOSE') and o.option_close is not None else (o.option_open if reason=='STOP' and o.option_open is not None and o.option_open<p.stop_loss else p.stop_loss if reason=='STOP' else o.option_last_price)
  fills=[_exit(i,i.exit_fill_ids[0],p.remaining_lot_count,price,reason,cost)]
 elif any(targets):
  prior={fill.fill_reason for fill in p.exit_fills};alloc=[0 if f'TARGET_{n+1}' in prior else lots for n,lots in enumerate((p.target_1_lot_count,p.target_2_lot_count,p.target_3_lot_count))]; indexes=[n for n,x in enumerate(targets) if x and alloc[n]>0]
  if policy.multiple_target_crossing_mode=='HIGHEST_CROSSED_TARGET' and indexes:indexes=list(range(max(indexes)+1))
  needed=len(indexes)+(1 if targets[2] and p.runner_lot_count and policy.runner_close_mode=='TARGET_3' else 0)+(1 if stop and policy.same_observation_precedence=='TARGET_FIRST' else 0)
  if len(i.exit_fill_ids)<needed:return PaperTradePositionEvaluationResultV1(**base,status='BLOCKED',position_decision='BLOCK',resulting_position=None,resulting_lifecycle_state=state,generated_exit_fills=(),pnl_evidence=None,blockers=('INSUFFICIENT_EXIT_FILL_IDS',))
  for n in indexes:
   lots=min(alloc[n],p.remaining_lot_count-sum(x.filled_lot_count for x in fills))
   if lots>0:fills.append(_exit(i,i.exit_fill_ids[len(fills)],lots,(p.target_1,p.target_2,p.target_3)[n] if policy.target_trigger_mode=='TOUCH' else o.option_close,f'TARGET_{n+1}',(i.target_1_exit_cost,i.target_2_exit_cost,i.target_3_exit_cost)[n],f'T{n+1}'))
  if fills and targets[2] and p.runner_lot_count and policy.runner_close_mode=='TARGET_3':
   used=sum(x.filled_lot_count for x in fills);runner=min(p.runner_lot_count,p.remaining_lot_count-used)
   if runner>0:fills.append(_exit(i,i.exit_fill_ids[len(fills)],runner,p.target_3 if policy.target_trigger_mode=='TOUCH' else o.option_close,'RUNNER_CLOSE',i.runner_exit_cost))
  if fills and stop and policy.same_observation_precedence=='TARGET_FIRST':
   used=sum(x.filled_lot_count for x in fills);left=p.remaining_lot_count-used
   if left>0:fills.append(_exit(i,i.exit_fill_ids[len(fills)],left,p.stop_loss if policy.stop_trigger_mode=='TOUCH' else o.option_close,'STOP',i.stop_exit_cost))
 if not fills:return _hold(i,base)
 exited=sum(x.filled_quantity for x in fills);remaining=p.remaining_quantity-exited; lots=remaining//p.lot_size; gross=sum((x.fill_price-p.entry_price)*x.filled_quantity for x in fills);allocated_before=p.estimated_total_trading_cost*(p.initial_quantity-p.remaining_quantity)/p.initial_quantity;allocated_after=p.estimated_total_trading_cost*(p.initial_quantity-remaining)/p.initial_quantity;entry_cost=allocated_after-allocated_before;exit_cost=sum(x.estimated_trading_cost for x in fills);net=gross-entry_cost-exit_cost;real_gross=p.realized_gross_pnl+gross;real_net=p.realized_net_pnl+net;unreal=(o.option_last_price-p.entry_price)*remaining;terminal=remaining==0
 state_name={'STOP':'CLOSED_STOP','SESSION_CLOSE':'CLOSED_SESSION','EXPIRY_CLOSE':'CLOSED_EXPIRY','INVALIDATION':'CLOSED_INVALIDATED','CANCELLED':'CANCELLED','RUNNER_CLOSE':'CLOSED_TARGET_3','TARGET_1':'CLOSED_TARGET_1','TARGET_2':'CLOSED_TARGET_2','TARGET_3':'CLOSED_TARGET_3'}.get(fills[-1].fill_reason, 'PARTIALLY_EXITED') if terminal else 'PARTIALLY_EXITED'
 new=replace(p,exit_fills=p.exit_fills+tuple(fills),remaining_quantity=remaining,remaining_lot_count=lots,lifecycle_state=state_name,realized_gross_pnl=real_gross,realized_net_pnl=real_net,unrealized_pnl=0. if terminal else unreal,total_pnl=real_net if terminal else real_net+unreal)
 ev=PaperTradePnlEvidenceV1(i.pnl_evidence_id,p.position_id,p.trade_plan_id,p.integrated_trade_plan_result_id,o.observation_id,p.entry_price,o.option_last_price,p.initial_quantity,remaining,p.initial_quantity-remaining,p.realized_gross_pnl,gross,real_gross,allocated_before,entry_cost,allocated_after,exit_cost,p.realized_net_pnl,net,real_net,0. if terminal else unreal,real_net if terminal else real_net+unreal,i.evaluation_timestamp)
 decision={'STOP':'CLOSE_STOP','SESSION_CLOSE':'CLOSE_SESSION','EXPIRY_CLOSE':'CLOSE_EXPIRY','INVALIDATION':'CLOSE_INVALIDATED','CANCELLED':'CANCEL','RUNNER_CLOSE':'CLOSE_TARGET_3'}.get(fills[-1].fill_reason, 'CLOSE_'+fills[-1].fill_reason if terminal else 'PARTIAL_EXIT')
 reasons=(i.invalidation_reason_code,) if reason=='INVALIDATION' else (i.cancellation_reason_code,) if reason=='CANCELLED' else ()
 return PaperTradePositionEvaluationResultV1(**base,status=state_name,position_decision=decision,resulting_position=new,resulting_lifecycle_state=_lifecycle(i,state_name,reason or fills[-1].fill_reason),generated_exit_fills=tuple(fills),pnl_evidence=ev,stop_triggered=reason=='STOP',target_1_triggered=bool(targets[0]) and reason is None,target_2_triggered=bool(targets[1]) and reason is None,target_3_triggered=bool(targets[2]) and reason is None,session_close_triggered=reason=='SESSION_CLOSE',expiry_close_triggered=reason=='EXPIRY_CLOSE',invalidation_triggered=reason=='INVALIDATION',cancellation_triggered=reason=='CANCELLED',decision_reasons=reasons)
def _hold(i,base,reason=None,order=True,economic_noop=False):
 p,o=i.position,i.observation;unreal=(o.option_last_price-p.entry_price)*p.remaining_quantity;new=replace(p,unrealized_pnl=unreal,total_pnl=p.realized_net_pnl+unreal)
 if economic_noop:return PaperTradePositionEvaluationResultV1(**base,status=p.lifecycle_state,position_decision='HOLD',resulting_position=p,resulting_lifecycle_state=i.lifecycle_state,generated_exit_fills=(),pnl_evidence=None,observation_order_valid=order,decision_reasons=((reason,) if reason else ()))
 allocated=p.estimated_total_trading_cost*(p.initial_quantity-p.remaining_quantity)/p.initial_quantity
 ev=PaperTradePnlEvidenceV1(i.pnl_evidence_id,p.position_id,p.trade_plan_id,p.integrated_trade_plan_result_id,o.observation_id,p.entry_price,o.option_last_price,p.initial_quantity,p.remaining_quantity,p.initial_quantity-p.remaining_quantity,p.realized_gross_pnl,0.,p.realized_gross_pnl,allocated,0.,allocated,0.,p.realized_net_pnl,0.,p.realized_net_pnl,unreal,p.realized_net_pnl+unreal,i.evaluation_timestamp)
 return PaperTradePositionEvaluationResultV1(**base,status=p.lifecycle_state,position_decision='HOLD',resulting_position=new,resulting_lifecycle_state=i.lifecycle_state,generated_exit_fills=(),pnl_evidence=ev,observation_order_valid=order,decision_reasons=((reason,) if reason else ()))
