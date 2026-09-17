from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
def _t(v,n):
 if type(v)is not str or not(v:=v.strip()):raise ValueError(n)
 return v
def _n(v,n,f=False):
 if type(v)not in(int,float) or isinstance(v,bool) or not math.isfinite(v) or v<0 or(f and v>1):raise ValueError(n)
 return float(v)
def _freeze(v):
 if v is None or type(v)in(bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_t(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in(tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class CapitalQuantityTradingCostPolicyV1:
 cost_policy_id:str;calculation_mode:str;brokerage_rate_fraction:float=0.;brokerage_fixed_per_order:float=0.;exchange_transaction_charge_fraction:float=0.;clearing_charge_fraction:float=0.;stt_rate_fraction:float=0.;sebi_charge_fraction:float=0.;stamp_duty_rate_fraction:float=0.;gst_rate_fraction:float=0.;slippage_rate_fraction:float=0.;estimated_order_count:int=1;apply_brokerage:bool=True;apply_exchange_transaction_charges:bool=True;apply_clearing_charges:bool=True;apply_stt:bool=True;apply_sebi_charges:bool=True;apply_stamp_duty:bool=True;apply_gst:bool=True;apply_slippage:bool=True;gst_taxable_base_mode:str='BROKERAGE_AND_SERVICE_CHARGES';policy_timestamp:datetime|None=None;policy_source:str='CALLER';warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  object.__setattr__(self,'cost_policy_id',_t(self.cost_policy_id,'cost_policy_id'))
  if self.calculation_mode not in {'CALLER_SUPPLIED_EVIDENCE','FIXED_ASSUMPTION_MODEL'} or self.gst_taxable_base_mode not in {'BROKERAGE_AND_SERVICE_CHARGES','CALLER_SUPPLIED'}:raise ValueError('mode')
  for n in ('brokerage_rate_fraction','exchange_transaction_charge_fraction','clearing_charge_fraction','stt_rate_fraction','sebi_charge_fraction','stamp_duty_rate_fraction','gst_rate_fraction','slippage_rate_fraction'):object.__setattr__(self,n,_n(getattr(self,n),n,True))
  object.__setattr__(self,'brokerage_fixed_per_order',_n(self.brokerage_fixed_per_order,'brokerage_fixed_per_order'))
  if type(self.estimated_order_count)is not int or isinstance(self.estimated_order_count,bool) or self.estimated_order_count<1:raise ValueError('estimated_order_count')
  if any(type(getattr(self,n))is not bool for n in self.__dataclass_fields__ if n.startswith('apply_')):raise TypeError('apply')
  if not isinstance(self.policy_timestamp,datetime) or self.policy_timestamp.tzinfo is None:raise ValueError('policy_timestamp')
  object.__setattr__(self,'policy_source',_t(self.policy_source,'policy_source'));object.__setattr__(self,'warnings',tuple(dict.fromkeys(_t(x,'warning') for x in self.warnings)))
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.policy_timestamp.isoformat() if n=='policy_timestamp' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(self.warnings) if n=='warnings' else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict();[d.pop(n) for n in ('cost_policy_id','policy_timestamp','source_timestamps')];return d
