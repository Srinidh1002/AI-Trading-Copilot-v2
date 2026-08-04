"""Immutable PAPER-only attachment of ranked P5 option candidates to planning constraints."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
from .option_contract_ranking_result_v1 import OptionContractRankingResultV1
from .option_contract_eligibility_evidence_v1 import OptionContractEligibilityEvidenceV1
_PAIR={'BULLISH':'CALL','BEARISH':'PUT'};_M={'ATM','ITM','OTM'}
def _s(v,n):
 if type(v)is not str or not v.strip():raise ValueError(n)
 return v
def _n(v,n,lo=0,positive=False):
 if type(v)not in (int,float) or not math.isfinite(v) or (v<=0 if positive else v<lo):raise ValueError(n)
 return float(v)
def _diag(v,n):
 if not isinstance(v,tuple):raise TypeError(n)
 o=[]
 for x in v:
  x=_s(x,n).strip()
  if x not in o:o.append(x)
 return tuple(o)
def _freeze(v):
 if v is None or type(v) in (bool,int,str):return v
 if type(v)is float and math.isfinite(v):return v
 if isinstance(v,Mapping):return MappingProxyType(dict(sorted((_s(k,'metadata key'),_freeze(x)) for k,x in v.items())))
 if type(v)in (tuple,list):return tuple(_freeze(x) for x in v)
 raise ValueError('metadata')
def _plain(v):return {k:_plain(v[k]) for k in sorted(v)} if isinstance(v,Mapping) else [_plain(x) for x in v] if isinstance(v,tuple) else v
@dataclass(frozen=True,slots=True)
class OptionContractSelectionInputV1:
 selection_id:str;selection_result_id:str;evaluated_at:datetime;trade_plan_input_id:str;policy_id:str;option_ranking_result_id:str;underlying_symbol:str;exchange:str;direction:str;option_right:str;option_ranking_result:OptionContractRankingResultV1;available_capital:float;maximum_entry_premium:float|None;maximum_spread_fraction:float|None;minimum_open_interest:int;minimum_volume:int;minimum_liquidity_score:float|None;allowed_moneyness:tuple[str,...];maximum_moneyness_steps:int;minimum_lot_count:int;maximum_lot_count:int;allow_weekly_expiry:bool;allow_monthly_expiry:bool;allow_same_day_expiry:bool;minimum_days_to_expiry:int;maximum_days_to_expiry:int|None;planning_allowed:bool;session_allows_new_entries:bool;event_restriction_active:bool;blockers:tuple[str,...]=();warnings:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);candidate_eligibility_evidence:tuple[OptionContractEligibilityEvidenceV1,...]=();execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('selection_id','selection_result_id','trade_plan_input_id','policy_id','option_ranking_result_id'):object.__setattr__(self,n,_s(getattr(self,n),n))
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None:raise ValueError('evaluated_at')
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None or self.direction not in _PAIR or self.option_right!=_PAIR[self.direction]:raise ValueError('identity')
  object.__setattr__(self,'underlying_symbol',i[0]);object.__setattr__(self,'exchange',i[1])
  r=self.option_ranking_result
  if type(r)is not OptionContractRankingResultV1 or r.ranking_id!=self.option_ranking_result_id or (r.underlying_symbol,r.exchange)!=i or r.directional_bias!=self.direction or r.required_option_type!=self.option_right:raise ValueError('ranking coherence')
  if not isinstance(self.candidate_eligibility_evidence,tuple):raise TypeError('candidate_eligibility_evidence')
  candidates={c.contract.contract_id:c for c in r.ranked_candidates}; evidence={}
  for item in self.candidate_eligibility_evidence:
   if type(item)is not OptionContractEligibilityEvidenceV1:raise TypeError('candidate eligibility evidence')
   if item.candidate_id in evidence or item.candidate_id not in candidates:raise ValueError('candidate eligibility evidence')
   c=candidates[item.candidate_id].contract
   if (item.underlying_symbol,item.exchange,item.option_right,item.trading_symbol,item.expiry_date)!=(c.underlying_symbol,c.exchange,c.option_type,c.trading_symbol,c.expiry_date) or abs(item.strike_price-c.strike)>1e-9:raise ValueError('candidate evidence coherence')
   evidence[item.candidate_id]=item
  object.__setattr__(self,'candidate_eligibility_evidence',tuple(evidence[c.contract.contract_id] for c in r.ranked_candidates if c.contract.contract_id in evidence))
  object.__setattr__(self,'available_capital',_n(self.available_capital,'capital',positive=True))
  for n in ('maximum_entry_premium','minimum_liquidity_score'):
   if getattr(self,n)is not None:object.__setattr__(self,n,_n(getattr(self,n),n,positive=(n=='maximum_entry_premium')))
  if self.maximum_spread_fraction is not None:object.__setattr__(self,'maximum_spread_fraction',_n(self.maximum_spread_fraction,'spread'))
  if self.maximum_spread_fraction is not None and self.maximum_spread_fraction>1:raise ValueError('spread')
  for n in ('minimum_open_interest','minimum_volume','maximum_moneyness_steps','minimum_days_to_expiry'):
   if type(getattr(self,n))is not int or getattr(self,n)<0:raise ValueError(n)
  m=tuple(_s(x,'moneyness').upper() for x in self.allowed_moneyness)
  if not m or len(set(m))!=len(m) or not set(m)<=_M:raise ValueError('moneyness')
  object.__setattr__(self,'allowed_moneyness',m)
  if type(self.minimum_lot_count)is not int or type(self.maximum_lot_count)is not int or self.minimum_lot_count<1 or self.maximum_lot_count<self.minimum_lot_count:raise ValueError('lots')
  if any(type(getattr(self,n))is not bool for n in ('allow_weekly_expiry','allow_monthly_expiry','allow_same_day_expiry','planning_allowed','session_allows_new_entries','event_restriction_active')) or not(self.allow_weekly_expiry or self.allow_monthly_expiry) or (not self.allow_same_day_expiry and self.minimum_days_to_expiry<1):raise ValueError('context')
  if self.maximum_days_to_expiry is not None and (type(self.maximum_days_to_expiry)is not int or self.maximum_days_to_expiry<self.minimum_days_to_expiry):raise ValueError('dte')
  object.__setattr__(self,'blockers',_diag(self.blockers,'blockers'));object.__setattr__(self,'warnings',_diag(self.warnings,'warnings'))
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 def get_candidate_eligibility_evidence(self,candidate_id):
  candidate_id=_s(candidate_id,'candidate_id')
  return next((item for item in self.candidate_eligibility_evidence if item.candidate_id==candidate_id),None)
 def to_dict(self):return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else self.option_ranking_result.to_dict() if n=='option_ranking_result' else [x.to_dict() for x in self.candidate_eligibility_evidence] if n=='candidate_eligibility_evidence' else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'allowed_moneyness','blockers','warnings'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('selection_id','selection_result_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
