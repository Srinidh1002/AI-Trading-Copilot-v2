from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from .paper_market_observation_v1 import _aware_datetime,_freeze_json_value,_freeze_warnings,_nonblank_text,_plain_json_value
@dataclass(frozen=True,slots=True)
class PaperTradePnlEvidenceV1:
 pnl_evidence_id:str;position_id:str;trade_plan_id:str;integrated_trade_plan_result_id:str;observation_id:str;entry_price:float;current_option_price:float;initial_quantity:int;remaining_quantity:int;exited_quantity:int;realized_gross_pnl_before:float;realized_gross_pnl_delta:float;realized_gross_pnl_after:float;allocated_entry_cost_before:float;allocated_entry_cost_delta:float;allocated_entry_cost_after:float;exit_trading_cost_delta:float;realized_net_pnl_before:float;realized_net_pnl_delta:float;realized_net_pnl_after:float;unrealized_pnl_after:float;total_pnl_after:float;calculated_at:datetime;warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('pnl_evidence_id','position_id','trade_plan_id','integrated_trade_plan_result_id','observation_id'):object.__setattr__(self,n,_nonblank_text(getattr(self,n),n))
  for n in ('initial_quantity','remaining_quantity','exited_quantity'):
   if type(getattr(self,n))is not int or getattr(self,n)<0:raise ValueError(n)
  if self.initial_quantity!=self.remaining_quantity+self.exited_quantity:raise ValueError('quantity')
  for n in ('entry_price','current_option_price','realized_gross_pnl_before','realized_gross_pnl_delta','realized_gross_pnl_after','allocated_entry_cost_before','allocated_entry_cost_delta','allocated_entry_cost_after','exit_trading_cost_delta','realized_net_pnl_before','realized_net_pnl_delta','realized_net_pnl_after','unrealized_pnl_after','total_pnl_after'):
   v=getattr(self,n)
   if type(v)not in (int,float) or isinstance(v,bool) or not math.isfinite(v):raise ValueError(n)
   object.__setattr__(self,n,float(v))
  if self.entry_price<=0 or self.current_option_price<=0 or self.allocated_entry_cost_delta<0 or self.exit_trading_cost_delta<0:raise ValueError('money')
  if not math.isclose(self.realized_gross_pnl_after,self.realized_gross_pnl_before+self.realized_gross_pnl_delta,abs_tol=1e-9) or not math.isclose(self.allocated_entry_cost_after,self.allocated_entry_cost_before+self.allocated_entry_cost_delta,abs_tol=1e-9) or not math.isclose(self.realized_net_pnl_after,self.realized_net_pnl_before+self.realized_net_pnl_delta,abs_tol=1e-9) or not math.isclose(self.total_pnl_after,self.realized_net_pnl_after+self.unrealized_pnl_after,abs_tol=1e-9):raise ValueError('pnl coherence')
  object.__setattr__(self,'calculated_at',_aware_datetime(self.calculated_at,'calculated_at'));object.__setattr__(self,'warnings',_freeze_warnings(self.warnings));object.__setattr__(self,'metadata',_freeze_json_value(self.metadata))
  if self.execution_mode!='PAPER'or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.calculated_at.isoformat()if n=='calculated_at'else list(self.warnings)if n=='warnings'else _plain_json_value(self.metadata)if n=='metadata'else getattr(self,n))for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop('pnl_evidence_id');return d
