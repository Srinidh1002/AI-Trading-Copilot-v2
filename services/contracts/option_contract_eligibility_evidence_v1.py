"""Caller-supplied, PAPER-only supplemental option eligibility evidence."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import date,datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
def _s(v,n):
 if type(v)is not str or not (v:=v.strip()):raise ValueError(n)
 return v
def _freeze(v):
 if v is None or type(v)in(bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_s(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in(tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class OptionContractEligibilityEvidenceV1:
 evidence_id:str;candidate_id:str;underlying_symbol:str;exchange:str;option_right:str;trading_symbol:str;strike_price:float;expiry_date:date;moneyness_steps:int;expiry_category:str;days_to_expiry:int;evidence_timestamp:datetime;evidence_source:str;warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('evidence_id','candidate_id','trading_symbol','evidence_source'):object.__setattr__(self,n,_s(getattr(self,n),n))
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None or self.option_right not in {'CALL','PUT'}:raise ValueError('identity')
  object.__setattr__(self,'underlying_symbol',i[0]);object.__setattr__(self,'exchange',i[1])
  if type(self.strike_price)not in(int,float) or not math.isfinite(self.strike_price) or self.strike_price<=0:raise ValueError('strike')
  object.__setattr__(self,'strike_price',float(self.strike_price))
  if type(self.expiry_date)is not date:raise ValueError('expiry_date')
  if type(self.moneyness_steps)is not int or self.moneyness_steps<0 or self.expiry_category not in {'WEEKLY','MONTHLY'} or type(self.days_to_expiry)is not int or self.days_to_expiry<0:raise ValueError('eligibility evidence')
  if not isinstance(self.evidence_timestamp,datetime) or self.evidence_timestamp.tzinfo is None:raise ValueError('timestamp')
  if not isinstance(self.warnings,tuple):raise TypeError('warnings')
  w=[]
  for x in self.warnings:
   x=_s(x,'warning')
   if x not in w:w.append(x)
  object.__setattr__(self,'warnings',tuple(w))
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('source timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def to_dict(self):return {n:(self.expiry_date.isoformat() if n=='expiry_date' else self.evidence_timestamp.isoformat() if n=='evidence_timestamp' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(self.warnings) if n=='warnings' else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('evidence_id','evidence_timestamp','source_timestamps'):d.pop(n)
  return d
