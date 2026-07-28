from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping
STATES={"PRE_OPEN","REGULAR","CLOSING","POST_CLOSE","CLOSED","HOLIDAY","WEEKEND","SPECIAL","UNKNOWN"}; PHASES={"BEFORE_PRE_OPEN","PRE_OPEN_ORDER_ENTRY","PRE_OPEN_MATCHING","PRE_OPEN_BUFFER","REGULAR_TRADING","CLOSING_SESSION","AFTER_MARKET","SPECIAL_TRADING","CLOSED_ALL_DAY","UNKNOWN"}; DAYS={"TRADING_DAY","WEEKEND","HOLIDAY","SPECIAL_TRADING_DAY","UNKNOWN"}
@dataclass(frozen=True,slots=True)
class MarketSessionValidationV1:
    validation_id:str; evaluated_at:datetime; market_timestamp:datetime; symbol:str; exchange:str; timezone:str; trading_date:date; session_state:str; session_phase:str; trading_day_status:str
    schema_version:str="market_session_validation.v1"; regular_open_at:datetime|None=None; regular_close_at:datetime|None=None; phase_started_at:datetime|None=None; phase_ends_at:datetime|None=None; is_trading_day:bool=False; regular_session_open:bool=False; analysis_allowed:bool=False; paper_preparation_allowed:bool=False; paper_execution_allowed:bool=False; timestamp_age_seconds:float|None=None; stale:bool=False; future_timestamp:bool=False; holiday_name:str|None=None; special_session:bool=False; special_session_name:str|None=None; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); errors:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.schema_version!="market_session_validation.v1" or not self.validation_id or self.session_state not in STATES or self.session_phase not in PHASES or self.trading_day_status not in DAYS: raise ValueError("Invalid market session validation contract.")
        if self.evaluated_at.tzinfo is None or self.market_timestamp.tzinfo is None: raise ValueError("Session timestamps must be timezone-aware.")
        if self.timestamp_age_seconds is not None and not math.isfinite(self.timestamp_age_seconds): raise ValueError("timestamp_age_seconds must be finite.")
        object.__setattr__(self,"metadata",dict(self.metadata))
    def to_dict(self):
        result={name:getattr(self,name) for name in self.__dataclass_fields__}; result["evaluated_at"]=self.evaluated_at.isoformat(); result["market_timestamp"]=self.market_timestamp.isoformat(); result["trading_date"]=self.trading_date.isoformat()
        for name in ("regular_open_at","regular_close_at","phase_started_at","phase_ends_at"):
            if result[name]: result[name]=result[name].isoformat()
        for name in ("blockers","warnings","errors"): result[name]=list(result[name])
        result["metadata"]=dict(sorted(self.metadata.items())); return result
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"))
    def semantic_dict(self):
        result=self.to_dict(); result.pop("validation_id"); result.pop("evaluated_at"); return result
