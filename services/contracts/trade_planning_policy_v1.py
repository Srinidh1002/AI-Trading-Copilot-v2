from __future__ import annotations
import json,math
from dataclasses import dataclass
def _s(v,n):
 if type(v)is not str or not(v:=v.strip()):raise ValueError(n)
 return v.upper()
def _n(v,n,p=False):
 if isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v)or(p and v<=0)or(not p and v<0):raise ValueError(n)
 return float(v)
@dataclass(frozen=True,slots=True)
class TradePlanningPolicyV1:
 policy_id:str;policy_name:str;policy_version:str;maximum_risk_fraction:float;minimum_risk_amount:float|None;maximum_risk_amount:float|None;stop_loss_method:str;stop_loss_atr_multiplier:float|None;stop_loss_premium_fraction:float|None;stop_loss_structure_buffer_fraction:float;minimum_stop_distance_fraction:float;maximum_stop_distance_fraction:float;entry_reference_method:str;entry_tolerance_below_fraction:float;entry_tolerance_above_fraction:float;maximum_chase_fraction:float;require_limit_entry:bool;minimum_reward_to_risk_t1:float;minimum_reward_to_risk_t2:float;minimum_reward_to_risk_t3:float;target_method:str;target_1_multiplier:float;target_2_multiplier:float;target_3_multiplier:float;target_1_allocation_fraction:float;target_2_allocation_fraction:float;target_3_allocation_fraction:float;maximum_entry_premium:float|None;maximum_spread_fraction:float;minimum_open_interest:int;minimum_volume:int;minimum_liquidity_score:float|None;allowed_moneyness:tuple[str,...];maximum_moneyness_steps:int;minimum_lot_count:int;maximum_lot_count:int;allow_partial_target_lots:bool;minimum_lots_for_three_targets:int;insufficient_target_lot_behavior:str;estimated_entry_slippage_fraction:float;estimated_exit_slippage_fraction:float;estimated_brokerage_per_order:float;estimated_other_charges_fraction:float;allow_weekly_expiry:bool;allow_monthly_expiry:bool;allow_same_day_expiry:bool;minimum_days_to_expiry:int;maximum_days_to_expiry:int|None;block_new_entries_during_high_impact_events:bool;event_pre_buffer_minutes:int;event_post_buffer_minutes:int;blocked_event_categories:tuple[str,...];require_market_open:bool;require_new_entries_allowed:bool;require_paper_execution_allowed:bool;block_special_sessions:bool;minimum_minutes_after_open:int;minimum_minutes_before_close:int;minimum_opportunity_confidence:float;minimum_option_confidence:float;minimum_plan_confidence:float;warnings_block_planning:bool;blocker_codes:tuple[str,...]=();warning_codes:tuple[str,...]=();execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('policy_id','policy_name','policy_version'):object.__setattr__(self,n,_s(getattr(self,n),n))
  for n in self.__dataclass_fields__:
   v=getattr(self,n)
   if n.endswith('fraction') or n.startswith('minimum_reward') or n.startswith('target_') and n.endswith('multiplier') or n.startswith('stop_loss_atr'):
    if v is not None: object.__setattr__(self,n,_n(v,n,n in {'maximum_risk_fraction','minimum_stop_distance_fraction','maximum_stop_distance_fraction','minimum_reward_to_risk_t1','minimum_reward_to_risk_t2','minimum_reward_to_risk_t3','target_1_multiplier','target_2_multiplier','target_3_multiplier','target_1_allocation_fraction','target_2_allocation_fraction','target_3_allocation_fraction','stop_loss_atr_multiplier'}))
  if not 0<self.maximum_risk_fraction<=1 or any(x>1 for x in (self.stop_loss_premium_fraction or 0,self.stop_loss_structure_buffer_fraction,self.minimum_stop_distance_fraction,self.maximum_stop_distance_fraction,self.entry_tolerance_below_fraction,self.entry_tolerance_above_fraction,self.maximum_chase_fraction,self.maximum_spread_fraction,self.estimated_entry_slippage_fraction,self.estimated_exit_slippage_fraction,self.estimated_other_charges_fraction,self.minimum_opportunity_confidence,self.minimum_option_confidence,self.minimum_plan_confidence)):raise ValueError('fraction')
  if self.minimum_risk_amount and self.maximum_risk_amount and self.maximum_risk_amount<self.minimum_risk_amount:raise ValueError('risk')
  if self.stop_loss_method not in {'ATR','STRUCTURE','PREMIUM_FRACTION','HYBRID'} or self.target_method not in {'RISK_MULTIPLE','ATR','EXPECTED_MOVE','STRUCTURE','HYBRID'} or self.entry_reference_method not in {'OPTION_MID','OPTION_ASK','LAST_TRADED_PRICE','SIGNAL_REFERENCE','HYBRID'}:raise ValueError('method')
  if self.stop_loss_method=='ATR' and self.stop_loss_atr_multiplier is None:raise ValueError('atr')
  if self.stop_loss_method=='PREMIUM_FRACTION' and self.stop_loss_premium_fraction is None:raise ValueError('premium')
  if not self.minimum_stop_distance_fraction<=self.maximum_stop_distance_fraction or not self.minimum_reward_to_risk_t1<=self.minimum_reward_to_risk_t2<=self.minimum_reward_to_risk_t3 or not self.target_1_multiplier<self.target_2_multiplier<self.target_3_multiplier or abs(sum((self.target_1_allocation_fraction,self.target_2_allocation_fraction,self.target_3_allocation_fraction))-1)>1e-9:raise ValueError('ordering')
  if not self.allow_weekly_expiry and not self.allow_monthly_expiry or (not self.allow_same_day_expiry and self.minimum_days_to_expiry<1):raise ValueError('expiry')
  if self.execution_mode!='PAPER'or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):
  return {n:list(getattr(self,n)) if isinstance(getattr(self,n),tuple) else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):return self.to_dict()
