"""Immutable post-CAS Task 9 session policy; evaluation remains a later concern."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from enum import Enum
from zoneinfo import ZoneInfo

class Task9MarketSegment(str,Enum):
 NSE_INDEX_CONTEXT="NSE_INDEX_CONTEXT";BSE_INDEX_CONTEXT="BSE_INDEX_CONTEXT";NFO_OPTIONS="NFO_OPTIONS";BFO_OPTIONS="BFO_OPTIONS";NSE_CASH_CONTEXT="NSE_CASH_CONTEXT";BSE_CASH_CONTEXT="BSE_CASH_CONTEXT"
class Task9SessionPhase(str,Enum): PRE_OPEN="PRE_OPEN";OPEN="OPEN";ENTRY_RESTRICTED="ENTRY_RESTRICTED";CLOSE_DRAIN="CLOSE_DRAIN";CLOSED="CLOSED";NON_TRADING_DAY="NON_TRADING_DAY";CAS_CONTEXT="CAS_CONTEXT"
def _text(v,n):
 if type(v)is not str or not v.strip():raise ValueError(n)
 return v.strip()
@dataclass(frozen=True,slots=True)
class Task9SegmentSessionWindowV1:
 segment:Task9MarketSegment;open_time:time;session_close:time;new_entry_cutoff:time|None;position_monitoring_until:time;cas_supported:bool=False;cas_start_time:time|None=None;cas_end_time:time|None=None;cas_reference_price_semantics:str|None=None
 def __post_init__(self):
  object.__setattr__(self,"segment",Task9MarketSegment(self.segment))
  if any(type(x)is not time for x in (self.open_time,self.session_close,self.position_monitoring_until)):raise ValueError("session time")
  if self.session_close<=self.open_time or self.position_monitoring_until>self.session_close:raise ValueError("session ordering")
  if self.new_entry_cutoff is not None and (type(self.new_entry_cutoff)is not time or self.new_entry_cutoff<=self.open_time or self.new_entry_cutoff>self.session_close):raise ValueError("new_entry_cutoff")
  if self.new_entry_cutoff is not None and self.position_monitoring_until<self.new_entry_cutoff:raise ValueError("monitoring")
  if self.segment in {Task9MarketSegment.NFO_OPTIONS,Task9MarketSegment.BFO_OPTIONS} and (self.open_time,self.session_close)!=(time(9,15),time(15,40)):raise ValueError("canonical F&O window")
  if (self.cas_start_time is None)!=(self.cas_end_time is None) or (self.cas_start_time is not None and self.cas_start_time>=self.cas_end_time):raise ValueError("CAS ordering")
 def to_dict(self):return {n:(getattr(self,n).value if n=="segment" else getattr(self,n).isoformat() if isinstance(getattr(self,n),time) else getattr(self,n)) for n in self.__dataclass_fields__}
 @classmethod
 def from_dict(cls,d):
  try:
   v=dict(d)
   for n in ("open_time","session_close","new_entry_cutoff","position_monitoring_until","cas_start_time","cas_end_time"):
    if v.get(n) is not None:v[n]=time.fromisoformat(v[n])
   return cls(**v)
  except (TypeError,ValueError,KeyError) as e:raise ValueError("session window serialization") from e
@dataclass(frozen=True,slots=True)
class Task9MarketSessionPolicyV1:
 policy_id:str;policy_version:str;timezone:str;calendar_authority_ref:str;windows:tuple[Task9SegmentSessionWindowV1,...]
 def __post_init__(self):
  for n in ("policy_id","policy_version","calendar_authority_ref"):object.__setattr__(self,n,_text(getattr(self,n),n))
  if self.timezone!="Asia/Kolkata":raise ValueError("timezone")
  ZoneInfo(self.timezone)
  if not isinstance(self.windows,tuple) or {x.segment for x in self.windows}!={x for x in Task9MarketSegment}:raise ValueError("segments")
  object.__setattr__(self,"windows",tuple(sorted(self.windows,key=lambda x:x.segment.value)))
 def to_dict(self):return {"policy_id":self.policy_id,"policy_version":self.policy_version,"timezone":self.timezone,"calendar_authority_ref":self.calendar_authority_ref,"windows":[x.to_dict() for x in sorted(self.windows,key=lambda x:x.segment.value)]}
 @classmethod
 def from_dict(cls,d):
  try:return cls(d["policy_id"],d["policy_version"],d["timezone"],d["calendar_authority_ref"],tuple(Task9SegmentSessionWindowV1.from_dict(x) for x in d["windows"]))
  except (TypeError,ValueError,KeyError) as e:raise ValueError("session policy serialization") from e
def build_task9_market_session_policy(*,policy_id,policy_version,calendar_authority_ref,nfo_new_entry_cutoff,bfo_new_entry_cutoff):
 if nfo_new_entry_cutoff is None or bfo_new_entry_cutoff is None:raise ValueError("explicit new-entry cutoffs required")
 f=lambda s,c:Task9SegmentSessionWindowV1(s,time(9,15),time(15,40),c,time(15,40))
 context=lambda s:Task9SegmentSessionWindowV1(s,time(9,15),time(15,40),None,time(15,40),cas_supported=True)
 return Task9MarketSessionPolicyV1(policy_id,policy_version,"Asia/Kolkata",calendar_authority_ref,(context(Task9MarketSegment.NSE_INDEX_CONTEXT),context(Task9MarketSegment.BSE_INDEX_CONTEXT),f(Task9MarketSegment.NFO_OPTIONS,nfo_new_entry_cutoff),f(Task9MarketSegment.BFO_OPTIONS,bfo_new_entry_cutoff),context(Task9MarketSegment.NSE_CASH_CONTEXT),context(Task9MarketSegment.BSE_CASH_CONTEXT)))
