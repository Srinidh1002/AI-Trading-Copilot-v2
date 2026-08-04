"""Immutable PAPER-only planning input; contains no planning or execution logic."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity
from .market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from .canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from .market_session_validation_v1 import MarketSessionValidationV1
from .external_market_context_result_v1 import ExternalMarketContextResultV1
from .option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1

def _text(v,n):
 if type(v) is not str or not (v:=' '.join(v.split())): raise ValueError(n)
 return v
def _num(v,n,lo=0,positive=False):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (v<=0 if positive else v<lo): raise ValueError(n)
 return float(v)
def _diagnostics(v,n):
 if not isinstance(v,tuple): raise TypeError(n)
 out=[]
 for x in v:
  x=_text(x,n).upper()
  if x not in out: out.append(x)
 return tuple(sorted(out))
def _safe(v):
 if isinstance(v,datetime): return v.isoformat()
 if isinstance(v,Mapping): return {str(k):_safe(x) for k,x in v.items()}
 if isinstance(v,tuple): return [_safe(x) for x in v]
 if hasattr(v,'to_dict'): return v.to_dict()
 return v
@dataclass(frozen=True,slots=True)
class CanonicalTradePlanInputV1:
 trade_plan_input_id:str; evaluated_at:datetime; underlying_symbol:str; exchange:str
 selected_market_opportunity:MarketOpportunityCandidateV1; market_regime:CanonicalMarketRegimeResultV1; market_session_validation:MarketSessionValidationV1
 option_chain_available:bool; external_context_available:bool; available_capital:float; maximum_risk_amount:float; maximum_risk_fraction:float
 maximum_entry_premium:float|None; maximum_slippage_fraction:float; maximum_spread_fraction:float; estimated_brokerage_per_order:float; minimum_lot_count:int; maximum_lot_count:int; allow_weekly_expiry:bool; allow_monthly_expiry:bool; allow_same_day_expiry:bool
 option_chain_intelligence:OptionChainIntelligenceResultV1|None=None; external_market_context:ExternalMarketContextResultV1|None=None; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); source_timestamps:Mapping[str,datetime]=field(default_factory=dict); metadata:Mapping[str,Any]=field(default_factory=dict); execution_mode:str='PAPER'; live_execution_eligible:bool=False; schema_version:str='1.0'
 def __post_init__(self):
  object.__setattr__(self,'trade_plan_input_id',_text(self.trade_plan_input_id,'trade_plan_input_id'))
  if not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None: raise ValueError('evaluated_at')
  identity=normalize_market_identity(self.underlying_symbol,self.exchange)
  if identity is None: raise ValueError('identity')
  object.__setattr__(self,'underlying_symbol',identity[0]); object.__setattr__(self,'exchange',identity[1])
  for n,t in (('selected_market_opportunity',MarketOpportunityCandidateV1),('market_regime',CanonicalMarketRegimeResultV1),('market_session_validation',MarketSessionValidationV1)):
   x=getattr(self,n)
   if type(x) is not t: raise TypeError(n)
   if (getattr(x,'underlying_symbol',getattr(x,'symbol',None)),x.exchange)!=identity: raise ValueError(n)
  c=self.selected_market_opportunity
  if c.market_regime != self.market_regime or c.market_session_validation != self.market_session_validation: raise ValueError('candidate coherence')
  if c.execution_mode!='PAPER' or c.live_execution_eligible is not False: raise ValueError('candidate paper')
  if type(self.option_chain_available) is not bool or type(self.external_context_available) is not bool: raise TypeError('availability')
  if (self.option_chain_intelligence is None)==self.option_chain_available: raise ValueError('option_chain availability')
  if (self.external_market_context is None)!= (not self.external_context_available) or self.external_market_context != c.external_market_context: raise ValueError('external context availability')
  if self.option_chain_intelligence is not None and (type(self.option_chain_intelligence) is not OptionChainIntelligenceResultV1 or (self.option_chain_intelligence.underlying_symbol,self.option_chain_intelligence.exchange)!=identity): raise ValueError('option_chain_intelligence')
  for n,t in (('external_market_context',ExternalMarketContextResultV1),):
   x=getattr(self,n)
   if x is not None and (type(x) is not t or (x.underlying_symbol,x.exchange)!=identity): raise ValueError(n)
  object.__setattr__(self,'available_capital',_num(self.available_capital,'available_capital',positive=True)); object.__setattr__(self,'maximum_risk_amount',_num(self.maximum_risk_amount,'maximum_risk_amount',positive=True)); object.__setattr__(self,'maximum_risk_fraction',_num(self.maximum_risk_fraction,'maximum_risk_fraction',positive=True))
  if self.maximum_risk_fraction>1 or self.maximum_risk_amount>self.available_capital or self.maximum_risk_amount>self.available_capital*self.maximum_risk_fraction+1e-9: raise ValueError('risk limits')
  if self.maximum_entry_premium is not None: object.__setattr__(self,'maximum_entry_premium',_num(self.maximum_entry_premium,'maximum_entry_premium',positive=True))
  for n in ('maximum_slippage_fraction','maximum_spread_fraction','estimated_brokerage_per_order'): object.__setattr__(self,n,_num(getattr(self,n),n))
  if self.maximum_slippage_fraction>1 or self.maximum_spread_fraction>1 or type(self.minimum_lot_count) is not int or type(self.maximum_lot_count) is not int or self.minimum_lot_count<1 or self.maximum_lot_count<self.minimum_lot_count: raise ValueError('constraints')
  if any(type(getattr(self,n)) is not bool for n in ('allow_weekly_expiry','allow_monthly_expiry','allow_same_day_expiry')): raise TypeError('expiry constraints')
  inherited=c.blockers+self.market_session_validation.blockers+(self.external_market_context.blockers if self.external_market_context else ())
  inherited_warnings=c.warnings+self.market_session_validation.warnings+(self.external_market_context.warnings if self.external_market_context else ())
  object.__setattr__(self,'blockers',tuple(sorted(set(_diagnostics(self.blockers,'blockers')+inherited)))); object.__setattr__(self,'warnings',tuple(sorted(set(_diagnostics(self.warnings,'warnings')+inherited_warnings))))
  stamps=dict(self.source_timestamps)
  if any(type(k) is not str or not isinstance(v,datetime) or v.tzinfo is None for k,v in stamps.items()): raise ValueError('source_timestamps')
  object.__setattr__(self,'source_timestamps',MappingProxyType(dict(sorted(stamps.items()))))
  try: safe=json.loads(json.dumps(dict(self.metadata),sort_keys=True,allow_nan=False))
  except (TypeError,ValueError) as e: raise ValueError('metadata') from e
  object.__setattr__(self,'metadata',MappingProxyType(safe))
  if self.execution_mode!='PAPER' or self.live_execution_eligible is not False or self.schema_version!='1.0': raise ValueError('paper')
 @property
 def planning_allowed(self): return not self.blockers and self.selected_market_opportunity.candidate_status in {'READY','READY_WITH_WARNINGS'} and self.selected_market_opportunity.analysis_allowed and self.selected_market_opportunity.new_entries_allowed and self.market_session_validation.paper_execution_allowed
 @property
 def trade_opportunity(self): return self.selected_market_opportunity.trade_opportunity
 def to_dict(self): return {n:_safe(getattr(self,n)) for n in self.__dataclass_fields__}|{'planning_allowed':self.planning_allowed}
 def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)
 def semantic_dict(self):
  d=self.to_dict(); d.pop('trade_plan_input_id'); d.pop('evaluated_at'); return d
