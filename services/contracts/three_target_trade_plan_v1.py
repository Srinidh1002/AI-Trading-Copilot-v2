from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
from .option_contract_candidate_v1 import OptionContractCandidateV1
from .trade_plan_target_v1 import TradePlanTargetV1
def _text(v,n):
 if type(v)is not str or not(v:=' '.join(v.split())):raise ValueError(n)
 return v
def _diag(v,n):
 if not isinstance(v,tuple):raise TypeError(n)
 out=[]
 for x in v:
  x=_text(x,n).upper()
  if x not in out:out.append(x)
 return tuple(out)
def _conf(v,n,required=True):
 if v is None and not required:return None
 if isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v)or not 0<=v<=1:raise ValueError(n)
 return float(v)
@dataclass(frozen=True,slots=True)
class ThreeTargetTradePlanV1:
 trade_plan_id:str;trade_plan_input_id:str;policy_id:str;selected_opportunity_id:str;evaluated_at:datetime;underlying_symbol:str;exchange:str;plan_status:str;market:str;instrument_type:str;direction:str;opportunity_confidence:float;option_confidence:float|None;plan_confidence:float;invalidation_rules:tuple[str,...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();decision_reasons:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0';selected_option_contract:OptionContractCandidateV1|None=None;entry_zone_lower:float|None=None;entry_zone_upper:float|None=None;entry_reference_price:float|None=None;entry_tolerance_fraction:float|None=None;maximum_chase_price:float|None=None;entry_method:str|None=None;stop_loss_price:float|None=None;stop_loss_method:str|None=None;stop_distance:float|None=None;stop_distance_fraction:float|None=None;target_1:TradePlanTargetV1|None=None;target_2:TradePlanTargetV1|None=None;target_3:TradePlanTargetV1|None=None;lot_size:int|None=None;lot_count:int|None=None;quantity:int|None=None;available_capital:float|None=None;required_capital:float|None=None;risk_amount:float|None=None;maximum_permissible_loss:float|None=None;estimated_entry_cost:float|None=None;estimated_exit_cost:float|None=None;estimated_total_charges:float|None=None;estimated_slippage_cost:float|None=None;expiry:date|None=None;days_to_expiry:int|None=None;expiry_category:str|None=None
 def __post_init__(self):
  for n in ('trade_plan_id','trade_plan_input_id','policy_id','selected_opportunity_id'):object.__setattr__(self,n,_text(getattr(self,n),n))
  if not isinstance(self.evaluated_at,datetime)or self.evaluated_at.tzinfo is None:raise ValueError('evaluated_at')
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None or self.market!=i[0]:raise ValueError('identity')
  object.__setattr__(self,'underlying_symbol',i[0]);object.__setattr__(self,'exchange',i[1])
  if self.plan_status not in {'READY','BLOCKED','NO_TRADE'} or self.instrument_type!='INDEX_OPTION' or self.direction not in {'BULLISH','BEARISH'}:raise ValueError('vocabulary')
  object.__setattr__(self,'opportunity_confidence',_conf(self.opportunity_confidence,'opportunity_confidence'));object.__setattr__(self,'option_confidence',_conf(self.option_confidence,'option_confidence',False));object.__setattr__(self,'plan_confidence',_conf(self.plan_confidence,'plan_confidence'))
  for n in ('invalidation_rules','blockers','warnings','decision_reasons'):object.__setattr__(self,n,_diag(getattr(self,n),n))
  if self.plan_status=='READY' and (self.blockers or not self.invalidation_rules or self.option_confidence is None):raise ValueError('READY')
  if self.plan_status=='BLOCKED' and not self.blockers:raise ValueError('BLOCKED')
  if self.plan_status=='NO_TRADE' and not self.decision_reasons:raise ValueError('NO_TRADE')
  stamps=dict(self.source_timestamps)
  if any(type(k)is not str or not k.strip() or not isinstance(v,datetime)or v.tzinfo is None for k,v in stamps.items()):raise ValueError('source_timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(stamps.items()))))
  try:safe=json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))
  except (TypeError,ValueError)as e:raise ValueError('metadata')from e
  object.__setattr__(self,'metadata',MappingProxyType(safe))
  if self.execution_mode!='PAPER'or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
  groups=((self.entry_zone_lower,self.entry_zone_upper,self.entry_reference_price,self.entry_tolerance_fraction,self.entry_method),(self.stop_loss_price,self.stop_loss_method,self.stop_distance,self.stop_distance_fraction),(self.target_1,self.target_2,self.target_3),(self.lot_size,self.lot_count,self.quantity,self.available_capital,self.required_capital,self.risk_amount,self.maximum_permissible_loss),(self.estimated_entry_cost,self.estimated_exit_cost,self.estimated_total_charges,self.estimated_slippage_cost),(self.expiry,self.days_to_expiry,self.expiry_category))
  if any(any(x is not None for x in g) and any(x is None for x in g) for g in groups):raise ValueError('partial plan group')
  if self.plan_status=='READY':
   if self.selected_option_contract is None or any(all(x is None for x in g) for g in groups):raise ValueError('READY plan fields')
   if type(self.selected_option_contract)is not OptionContractCandidateV1:raise TypeError('selected_option_contract')
   con=self.selected_option_contract.contract
   if (con.underlying_symbol,con.exchange)!=(i) or (self.direction=='BULLISH' and con.option_type!='CALL') or (self.direction=='BEARISH' and con.option_type!='PUT'):raise ValueError('contract coherence')
   if type(self.expiry) is not date or isinstance(self.expiry,datetime) or type(self.days_to_expiry)is not int or self.days_to_expiry<0 or self.expiry_category not in {'WEEKLY','MONTHLY'} or self.expiry!=con.expiry_date:raise ValueError('expiry')
   if not self.entry_zone_lower<self.entry_zone_upper or not self.entry_zone_lower<=self.entry_reference_price<=self.entry_zone_upper or self.stop_loss_price>=self.entry_reference_price or abs(self.stop_distance-(self.entry_reference_price-self.stop_loss_price))>1e-8:raise ValueError('price geometry')
   ts=(self.target_1,self.target_2,self.target_3)
   if any(type(t)is not TradePlanTargetV1 for t in ts) or [t.target_number for t in ts]!=[1,2,3] or not ts[0].target_price<ts[1].target_price<ts[2].target_price or any(t.target_price<=self.entry_reference_price for t in ts) or abs(sum(t.allocation_fraction for t in ts)-1)>1e-8:raise ValueError('targets')
   if any(type(x)is not int or x<1 for x in (self.lot_size,self.lot_count,self.quantity)) or self.quantity!=self.lot_size*self.lot_count or self.required_capital>self.available_capital or self.risk_amount>self.maximum_permissible_loss:raise ValueError('sizing')
 @property
 def reward_to_risk_t1(self):return self.target_1.reward_to_risk if self.target_1 else None
 @property
 def reward_to_risk_t2(self):return self.target_2.reward_to_risk if self.target_2 else None
 @property
 def reward_to_risk_t3(self):return self.target_3.reward_to_risk if self.target_3 else None
 def to_dict(self):
  d={n:getattr(self,n)for n in self.__dataclass_fields__};d['evaluated_at']=self.evaluated_at.isoformat();d['source_timestamps']={k:v.isoformat()for k,v in self.source_timestamps.items()};d['expiry']=self.expiry.isoformat() if self.expiry else None
  for n in ('selected_option_contract','target_1','target_2','target_3'):
   if d[n] is not None:d[n]=d[n].to_dict()
  for n in ('invalidation_rules','blockers','warnings','decision_reasons'):d[n]=list(d[n])
  d['metadata']=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('trade_plan_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
