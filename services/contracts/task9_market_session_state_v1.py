from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime,time
from services.contracts.task9_market_session_policy_v1 import Task9MarketSegment,Task9SessionPhase
@dataclass(frozen=True,slots=True)
class Task9SegmentSessionStateV1:
 segment:Task9MarketSegment;market_date:date;evaluated_at:datetime;timezone:str;phase:Task9SessionPhase;market_open:bool;new_entries_allowed:bool;position_monitoring_allowed:bool;close_drain_required:bool;session_open_time:time;new_entry_cutoff:time|None;position_monitoring_until:time;session_close_time:time;calendar_status:str;policy_id:str;policy_version:str
 def __post_init__(self):
  object.__setattr__(self,"segment",Task9MarketSegment(self.segment));object.__setattr__(self,"phase",Task9SessionPhase(self.phase))
  if type(self.market_date)is not date or not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None or self.timezone!="Asia/Kolkata" or not self.policy_id or not self.policy_version:raise ValueError("session state identity")
  expected={Task9SessionPhase.PRE_OPEN:(False,False,False),Task9SessionPhase.OPEN:(True,True,True),Task9SessionPhase.ENTRY_RESTRICTED:(True,False,True),Task9SessionPhase.CLOSED:(False,False,False),Task9SessionPhase.NON_TRADING_DAY:(False,False,False)}
  if self.phase in expected and (self.market_open,self.new_entries_allowed,self.position_monitoring_allowed)!=expected[self.phase]:raise ValueError("inconsistent session state")
 def to_dict(self):return {n:(getattr(self,n).value if n in {"segment","phase"} else getattr(self,n).isoformat() if isinstance(getattr(self,n),(date,datetime,time)) else getattr(self,n)) for n in self.__dataclass_fields__}
 @classmethod
 def from_dict(cls,d):
  try:
   v=dict(d);v["market_date"]=date.fromisoformat(v["market_date"]);v["evaluated_at"]=datetime.fromisoformat(v["evaluated_at"])
   for n in ("session_open_time","new_entry_cutoff","position_monitoring_until","session_close_time"):
    if v.get(n) is not None:v[n]=time.fromisoformat(v[n])
   return cls(**v)
  except (KeyError,TypeError,ValueError) as e:raise ValueError("segment session state serialization") from e
@dataclass(frozen=True,slots=True)
class Task9MarketSessionStateV1:
 evaluated_at:datetime;market_date:date;timezone:str;states:tuple[Task9SegmentSessionStateV1,...]
 def __post_init__(self):
  if self.timezone!="Asia/Kolkata" or not isinstance(self.evaluated_at,datetime) or self.evaluated_at.tzinfo is None or type(self.market_date)is not date:raise ValueError("market session state")
  if not isinstance(self.states,tuple) or len({x.segment for x in self.states})!=len(self.states):raise ValueError("market session segments")
  if any((x.market_date,x.timezone,x.evaluated_at)!=(self.market_date,self.timezone,self.evaluated_at) for x in self.states):raise ValueError("market session child mismatch")
 def to_dict(self):return {"evaluated_at":self.evaluated_at.isoformat(),"market_date":self.market_date.isoformat(),"timezone":self.timezone,"states":[x.to_dict() for x in self.states]}
 @classmethod
 def from_dict(cls,d):
  try:return cls(datetime.fromisoformat(d["evaluated_at"]),date.fromisoformat(d["market_date"]),d["timezone"],tuple(Task9SegmentSessionStateV1.from_dict(x) for x in d["states"]))
  except (KeyError,TypeError,ValueError) as e:raise ValueError("market session state serialization") from e
