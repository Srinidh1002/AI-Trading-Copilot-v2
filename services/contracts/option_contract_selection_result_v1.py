from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity
from .option_contract_candidate_v1 import OptionContractCandidateV1
from .option_contract_selection_input_v1 import _s,_diag,_freeze,_plain
_PAIR={'BULLISH':'CALL','BEARISH':'PUT'};_FLAGS=('premium_affordable','spread_acceptable','liquidity_acceptable','open_interest_acceptable','volume_acceptable','moneyness_acceptable','expiry_acceptable','lot_size_acceptable','session_acceptable','event_acceptable')
@dataclass(frozen=True,slots=True)
class OptionContractSelectionResultV1:
 selection_result_id:str;selection_id:str;evaluated_at:datetime;underlying_symbol:str;exchange:str;direction:str;option_right:str;status:str;selected_contract:OptionContractCandidateV1|None;selected_rank:int|None;selected_score:float|None;selected_reason_codes:tuple[str,...]=();premium_affordable:bool|None=None;spread_acceptable:bool|None=None;liquidity_acceptable:bool|None=None;open_interest_acceptable:bool|None=None;volume_acceptable:bool|None=None;moneyness_acceptable:bool|None=None;expiry_acceptable:bool|None=None;lot_size_acceptable:bool|None=None;session_acceptable:bool|None=None;event_acceptable:bool|None=None;effective_maximum_entry_premium:float|None=None;effective_maximum_spread_fraction:float|None=None;estimated_one_lot_premium_cost:float|None=None;affordable_lot_count:int|None=None;blockers:tuple[str,...]=();warnings:tuple[str,...]=();decision_reasons:tuple[str,...]=();source_timestamps:Mapping[str,datetime]=field(default_factory=dict);metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str='PAPER';live_execution_eligible:bool=False;schema_version:str='1.0'
 def __post_init__(self):
  for n in ('selection_result_id','selection_id'):object.__setattr__(self,n,_s(getattr(self,n),n))
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None:raise ValueError('time')
  i=normalize_market_identity(self.underlying_symbol,self.exchange)
  if i is None or self.direction not in _PAIR or self.option_right!=_PAIR[self.direction] or self.status not in {'READY','BLOCKED','NO_CONTRACT'}:raise ValueError('identity/status')
  object.__setattr__(self,'underlying_symbol',i[0]);object.__setattr__(self,'exchange',i[1])
  g=(self.selected_contract,self.selected_rank,self.selected_score)
  if any(x is not None for x in g) and any(x is None for x in g):raise ValueError('partial selected group')
  if all(x is not None for x in g):
   if type(self.selected_contract)is not OptionContractCandidateV1 or type(self.selected_rank)is not int or self.selected_rank<1 or type(self.selected_score)not in (int,float) or not math.isfinite(self.selected_score) or (self.selected_contract.contract.underlying_symbol,self.selected_contract.contract.exchange)!=(i) or self.selected_contract.contract.option_type!=self.option_right:raise ValueError('selected group')
   object.__setattr__(self,'selected_score',float(self.selected_score))
  for n in _FLAGS:
   if getattr(self,n) is not None and type(getattr(self,n))is not bool:raise TypeError(n)
  for n,maxv,pos in (('effective_maximum_entry_premium',None,True),('effective_maximum_spread_fraction',1,False),('estimated_one_lot_premium_cost',None,True)):
   v=getattr(self,n)
   if v is not None and (type(v)not in (int,float) or not math.isfinite(v) or (v<=0 if pos else not 0<=v<=maxv)):raise ValueError(n)
   if v is not None:object.__setattr__(self,n,float(v))
  if self.affordable_lot_count is not None and (type(self.affordable_lot_count)is not int or self.affordable_lot_count<0 or self.estimated_one_lot_premium_cost is None):raise ValueError('affordability')
  for n in ('selected_reason_codes','blockers','warnings','decision_reasons'):object.__setattr__(self,n,_diag(getattr(self,n),n))
  if self.status=='READY' and (any(x is None for x in g) or self.blockers or not all(getattr(self,n) is True for n in _FLAGS) or self.estimated_one_lot_premium_cost is None or self.affordable_lot_count is None or self.affordable_lot_count<1):raise ValueError('READY')
  if self.status=='BLOCKED' and (not self.blockers or any(x is not None for x in g)):raise ValueError('BLOCKED')
  if self.status=='NO_CONTRACT' and (not self.decision_reasons or self.blockers or any(x is not None for x in g)):raise ValueError('NO_CONTRACT')
  if not isinstance(self.source_timestamps,Mapping) or any(type(k)is not str or not k.strip() or not isinstance(v,datetime) or v.tzinfo is None for k,v in self.source_timestamps.items()):raise ValueError('timestamps')
  from types import MappingProxyType
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(self.source_timestamps.items()))));object.__setattr__(self,'metadata',_freeze(self.metadata))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0':raise ValueError('paper')
 @property
 def selected_trading_symbol(self):return None if self.selected_contract is None else self.selected_contract.contract.trading_symbol
 @property
 def selected_strike(self):return None if self.selected_contract is None else self.selected_contract.contract.strike
 @property
 def selected_expiry(self):return None if self.selected_contract is None else self.selected_contract.contract.expiry_date
 @property
 def selected_lot_size(self):return None if self.selected_contract is None else self.selected_contract.contract.lot_size
 @property
 def selected_premium(self):return None if self.selected_contract is None else self.selected_contract.contract.last_price
 def to_dict(self):return {n:(self.evaluated_at.isoformat() if n=='evaluated_at' else self.selected_contract.to_dict() if n=='selected_contract' and self.selected_contract else {k:v.isoformat() for k,v in self.source_timestamps.items()} if n=='source_timestamps' else _plain(self.metadata) if n=='metadata' else list(getattr(self,n)) if n in {'selected_reason_codes','blockers','warnings','decision_reasons'} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict()
  for n in ('selection_result_id','selection_id','evaluated_at','source_timestamps'):d.pop(n)
  return d
