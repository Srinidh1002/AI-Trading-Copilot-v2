"""Immutable provider-neutral structured external-market observation."""
from __future__ import annotations
import json,math
from dataclasses import dataclass,field
from datetime import datetime
from types import MappingProxyType
from typing import Any,Mapping
from services.core.market_identity import normalize_market_identity,SUPPORTED_MARKET_IDENTITIES
_MAP={"GIFT_NIFTY":({"PREMARKET_INDICATOR","INDEX_FUTURE"},{"INDIA","GLOBAL"},{"EQUITY_INDEX_FUTURE"}),"SP500":({"INDEX_CLOSE","INDEX_FUTURE"},{"UNITED_STATES"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"NASDAQ":({"INDEX_CLOSE","INDEX_FUTURE"},{"UNITED_STATES"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"DOW_JONES":({"INDEX_CLOSE","INDEX_FUTURE"},{"UNITED_STATES"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"NIKKEI_225":({"INDEX_CLOSE","INDEX_FUTURE"},{"ASIA"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"HANG_SENG":({"INDEX_CLOSE","INDEX_FUTURE"},{"ASIA"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"SHANGHAI_COMPOSITE":({"INDEX_CLOSE","INDEX_FUTURE"},{"ASIA"},{"EQUITY_INDEX","EQUITY_INDEX_FUTURE"}),"DXY":({"FX_INDEX"},{"GLOBAL","UNITED_STATES"},{"FX"}),"BRENT_CRUDE":({"COMMODITY"},{"GLOBAL"},{"COMMODITY"}),"WTI_CRUDE":({"COMMODITY"},{"GLOBAL"},{"COMMODITY"}),"US_10Y_YIELD":({"BOND_YIELD"},{"UNITED_STATES"},{"FIXED_INCOME"}),"INDIA_10Y_YIELD":({"BOND_YIELD"},{"INDIA"},{"FIXED_INCOME"})}
_SESSION={"CURRENT_SESSION","PREVIOUS_SESSION_CLOSE","PREMARKET","OVERNIGHT","INTRADAY","DELAYED_INTRADAY","UNAVAILABLE"};_DIR={"POSITIVE","NEGATIVE","FLAT","UNAVAILABLE"};_STATUS={"READY","READY_WITH_WARNINGS","DELAYED","STALE","UNAVAILABLE","BLOCKED"}
def _text(v,n,u=False):
 if not isinstance(v,str):raise TypeError(f"{n} must be a string")
 v=v.strip()
 if not v:raise ValueError(f"{n} must not be empty")
 return v.upper() if u else v
def _time(v,n):
 if not isinstance(v,datetime):raise TypeError(f"{n} must be a datetime")
 if v.tzinfo is None or v.utcoffset() is None:raise ValueError(f"{n} must be timezone-aware")
 return v
def _msgs(v,n):
 if not isinstance(v,tuple):raise TypeError(f"{n} must be a tuple")
 v=tuple(_text(x,f"{n} item") for x in v)
 if len(v)!=len(set(v)):raise ValueError(f"{n} must not contain duplicates")
 return v
def _meta(v):
 if not isinstance(v,Mapping):raise TypeError("metadata must be a mapping")
 try:return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
 except (TypeError,ValueError) as e:raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class ExternalMarketObservationV1:
 external_market_observation_id:str;created_at:datetime;canonical_name:str;observation_type:str;market_region:str;asset_class:str;source_id:str;source_timestamp:datetime;session_reference:str;current_value:float|None;previous_value:float|None;change_value:float|None;change_percent:float|None;direction:str;observation_status:str;is_delayed:bool=False;delay_seconds:float=0.;affected_market_identities:tuple[tuple[str,str],...]=();blockers:tuple[str,...]=();warnings:tuple[str,...]=();metadata:Mapping[str,Any]=field(default_factory=dict);execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="external_market_observation.v1"
 def __post_init__(self):
  for n in ("external_market_observation_id","source_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  object.__setattr__(self,"created_at",_time(self.created_at,"created_at"));object.__setattr__(self,"source_timestamp",_time(self.source_timestamp,"source_timestamp"))
  name=_text(self.canonical_name,"canonical_name",True)
  if name not in _MAP:raise ValueError("unsupported canonical_name")
  for n,allowed in (("observation_type",_MAP[name][0]),("market_region",_MAP[name][1]),("asset_class",_MAP[name][2]),("session_reference",_SESSION),("direction",_DIR),("observation_status",_STATUS)):
   v=_text(getattr(self,n),n,True)
   if v not in allowed:raise ValueError(f"unsupported {n}")
   object.__setattr__(self,n,v)
  object.__setattr__(self,"canonical_name",name)
  for n in ("current_value","previous_value","change_value","change_percent"):
   v=getattr(self,n)
   if v is not None:
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise TypeError(f"{n} must be numeric or None")
    v=float(v)
    if not math.isfinite(v):raise ValueError(f"{n} must be finite")
   object.__setattr__(self,n,v)
  if self.current_value is not None and self.previous_value is not None:
   expected=self.current_value-self.previous_value
   if self.change_value is not None and not math.isclose(self.change_value,expected,abs_tol=1e-9):raise ValueError("change_value is inconsistent")
   if self.previous_value==0 and self.change_percent is not None:raise ValueError("zero previous value cannot support change_percent")
   if self.previous_value!=0 and self.change_percent is not None and not math.isclose(self.change_percent,expected/abs(self.previous_value)*100,abs_tol=1e-9):raise ValueError("change_percent is inconsistent")
  if isinstance(self.delay_seconds,bool) or not isinstance(self.delay_seconds,(int,float)) or not math.isfinite(float(self.delay_seconds)) or self.delay_seconds<0:raise ValueError("delay_seconds must be finite and non-negative")
  if not isinstance(self.is_delayed,bool):raise TypeError("is_delayed must be boolean")
  identities=[]
  if not isinstance(self.affected_market_identities,tuple):raise TypeError("affected_market_identities must be a tuple")
  for pair in self.affected_market_identities:
   if not isinstance(pair,tuple) or len(pair)!=2 or normalize_market_identity(*pair) not in SUPPORTED_MARKET_IDENTITIES:raise ValueError("unsupported affected market identity")
   identities.append(normalize_market_identity(*pair))
  if len(set(identities))!=len(identities) or tuple(identities)!=tuple(sorted(identities)):raise ValueError("affected identities must be unique and ordered")
  object.__setattr__(self,"affected_market_identities",tuple(identities));object.__setattr__(self,"blockers",_msgs(self.blockers,"blockers"));object.__setattr__(self,"warnings",_msgs(self.warnings,"warnings"));object.__setattr__(self,"metadata",_meta(self.metadata))
  if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="external_market_observation.v1":raise ValueError("external observation is paper-only v1")
  if self.observation_status=="READY" and (self.blockers or self.warnings or self.current_value is None or self.is_delayed):raise ValueError("READY observation is contradictory")
  if self.observation_status=="READY_WITH_WARNINGS" and (self.blockers or not self.warnings or self.current_value is None):raise ValueError("READY_WITH_WARNINGS observation is contradictory")
  if self.observation_status=="DELAYED" and (not self.is_delayed or self.delay_seconds<=0 or not self.warnings):raise ValueError("DELAYED observation requires delayed warning")
  if self.observation_status=="BLOCKED" and not self.blockers:raise ValueError("BLOCKED observation requires blockers")
  if self.observation_status=="UNAVAILABLE" and self.direction!="UNAVAILABLE":raise ValueError("UNAVAILABLE observation requires unavailable direction")
 def to_dict(self):
  d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","blockers","warnings","metadata","affected_market_identities"}};d["created_at"]=self.created_at.isoformat();d["source_timestamp"]=self.source_timestamp.isoformat();d["affected_market_identities"]=[list(x) for x in self.affected_market_identities];d["blockers"]=list(self.blockers);d["warnings"]=list(self.warnings);d["metadata"]=dict(self.metadata);return d
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("external_market_observation_id");d.pop("created_at");return d
