from __future__ import annotations
import json
from dataclasses import dataclass
from services.contracts.option_contract_selection_input_v1 import OptionContractSelectionInputV1
from services.contracts.trade_planning_policy_v1 import TradePlanningPolicyV1
@dataclass(frozen=True,slots=True)
class OptionContractSelectionConstraintsV1:
 policy_id:str;effective_maximum_entry_premium:float|None;effective_maximum_spread_fraction:float|None;effective_minimum_open_interest:int;effective_minimum_volume:int;effective_minimum_liquidity_score:float|None;effective_allowed_moneyness:tuple[str,...];effective_maximum_moneyness_steps:int;effective_minimum_lot_count:int;effective_maximum_lot_count:int;effective_allow_weekly_expiry:bool;effective_allow_monthly_expiry:bool;effective_allow_same_day_expiry:bool;effective_minimum_days_to_expiry:int;effective_maximum_days_to_expiry:int|None;is_coherent:bool;incoherence_codes:tuple[str,...];schema_version:str='1.0'
 def to_dict(self):return {n:list(getattr(self,n)) if isinstance(getattr(self,n),tuple) else getattr(self,n) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):return self.to_dict()
def resolve_option_contract_selection_constraints(selection_input,policy):
 if type(selection_input)is not OptionContractSelectionInputV1:raise TypeError('selection_input')
 if type(policy)is not TradePlanningPolicyV1:raise TypeError('policy')
 def lo(a,b):return min(x for x in (a,b) if x is not None) if a is not None or b is not None else None
 def hi(a,b):return max(x for x in (a,b) if x is not None) if a is not None or b is not None else None
 allowed=tuple(x for x in ('ATM','ITM','OTM') if x in selection_input.allowed_moneyness and x in policy.allowed_moneyness)
 dte_max=lo(selection_input.maximum_days_to_expiry,policy.maximum_days_to_expiry);codes=[]
 if selection_input.policy_id!=policy.policy_id or selection_input.execution_mode!='PAPER' or policy.execution_mode!='PAPER' or selection_input.live_execution_eligible is not False or policy.live_execution_eligible is not False:codes+=['CONTRACT_POLICY_MISMATCH']
 minlot=max(selection_input.minimum_lot_count,policy.minimum_lot_count);maxlot=min(selection_input.maximum_lot_count,policy.maximum_lot_count);mindte=max(selection_input.minimum_days_to_expiry,policy.minimum_days_to_expiry);weekly=selection_input.allow_weekly_expiry and policy.allow_weekly_expiry;monthly=selection_input.allow_monthly_expiry and policy.allow_monthly_expiry;sameday=selection_input.allow_same_day_expiry and policy.allow_same_day_expiry
 if not allowed:codes+=['CONTRACT_POLICY_MONEYNESS_EMPTY']
 if minlot>maxlot:codes+=['CONTRACT_POLICY_LOT_BOUNDS_INVALID']
 if dte_max is not None and mindte>dte_max:codes+=['CONTRACT_POLICY_DTE_BOUNDS_INVALID']
 if not weekly and not monthly:codes+=['CONTRACT_POLICY_EXPIRY_EMPTY']
 if not sameday and mindte==0:codes+=['CONTRACT_POLICY_SAME_DAY_INCOHERENT']
 return OptionContractSelectionConstraintsV1(policy.policy_id,lo(selection_input.maximum_entry_premium,policy.maximum_entry_premium),lo(selection_input.maximum_spread_fraction,policy.maximum_spread_fraction),max(selection_input.minimum_open_interest,policy.minimum_open_interest),max(selection_input.minimum_volume,policy.minimum_volume),hi(selection_input.minimum_liquidity_score,policy.minimum_liquidity_score),allowed,min(selection_input.maximum_moneyness_steps,policy.maximum_moneyness_steps),minlot,maxlot,weekly,monthly,sameday,mindte,dte_max,not codes,tuple(codes))
