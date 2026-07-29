from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
import json,math
from .capital_quantity_trading_cost_policy_v1 import _t,_n,_freeze,_plain
@dataclass(frozen=True,slots=True)
class CapitalQuantityTradingCostEvidenceV1:
 evidence_id:str;planning_input_id:str;trade_plan_id:str;cost_policy_id:str;option_selection_result_id:str;planned_lot_count:int;lot_size:int;planned_quantity:int;estimated_premium_outlay:float;estimated_order_count:int;estimated_brokerage:float;estimated_exchange_transaction_charges:float;estimated_clearing_charges:float;estimated_stt:float;estimated_sebi_charges:float;estimated_stamp_duty:float;estimated_gst:float;estimated_slippage:float;estimated_total_trading_cost:float;estimated_total_capital_requirement:float;applied_slippage_rate_fraction:float|None;applied_effective_cost_fraction:float|None;evidence_timestamp:datetime;evidence_source:str;warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('evidence_id','planning_input_id','trade_plan_id','cost_policy_id','option_selection_result_id','evidence_source'):object.__setattr__(self,n,_t(getattr(self,n),n))
  for n in ('planned_lot_count','lot_size','planned_quantity','estimated_order_count'):
   if type(getattr(self,n))is not int or isinstance(getattr(self,n),bool) or getattr(self,n)<1:raise ValueError(n)
  if self.planned_quantity!=self.planned_lot_count*self.lot_size:raise ValueError('quantity')
  names=('estimated_premium_outlay','estimated_brokerage','estimated_exchange_transaction_charges','estimated_clearing_charges','estimated_stt','estimated_sebi_charges','estimated_stamp_duty','estimated_gst','estimated_slippage','estimated_total_trading_cost','estimated_total_capital_requirement')
  for n in names:object.__setattr__(self,n,_n(getattr(self,n),n))
  components=sum(getattr(self,n) for n in names[1:9])
  if abs(self.estimated_total_trading_cost-components)>1e-9 or abs(self.estimated_total_capital_requirement-(self.estimated_premium_outlay+self.estimated_total_trading_cost))>1e-9:raise ValueError('totals')
  for n in ('applied_slippage_rate_fraction','applied_effective_cost_fraction'):
   if getattr(self,n)is not None:object.__setattr__(self,n,_n(getattr(self,n),n,True))
  if not isinstance(self.evidence_timestamp,datetime) or self.evidence_timestamp.tzinfo is None:raise ValueError('evidence_timestamp')
  object.__setattr__(self,'warnings',tuple(dict.fromkeys(_t(x,'warning') for x in self.warnings)));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.evidence_timestamp.isoformat() if n=='evidence_timestamp' else _plain(self.metadata) if n=='metadata' else list(self.warnings) if n=='warnings' else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
