"""Durable, deterministic authority records for Task 9 campaign rollover."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

class Task9CampaignRolloverAction(str, Enum):
    CONTINUE_CURRENT_RUN="CONTINUE_CURRENT_RUN"; START_NEW_OFFICIAL_RUN="START_NEW_OFFICIAL_RUN"; ADVANCE_TO_NEXT_MARKET_DAY="ADVANCE_TO_NEXT_MARKET_DAY"; RESUME_PAUSED_CAMPAIGN="RESUME_PAUSED_CAMPAIGN"; REMAIN_HALTED="REMAIN_HALTED"; CAMPAIGN_NUMERIC_TARGET_MET="CAMPAIGN_NUMERIC_TARGET_MET"; CAMPAIGN_TERMINAL_NO_CONTINUATION="CAMPAIGN_TERMINAL_NO_CONTINUATION"
class Task9CampaignRolloverReceiptStatus(str, Enum):
    PLANNED="PLANNED"; RUN_MANIFEST_PERSISTED="RUN_MANIFEST_PERSISTED"; POINTER_UPDATED="POINTER_UPDATED"; APPLIED="APPLIED"
_NEW=frozenset({Task9CampaignRolloverAction.START_NEW_OFFICIAL_RUN,Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY})
def _text(v,n):
    if type(v) is not str or not v.strip(): raise ValueError(n)
    return v.strip()
def derive_task9_campaign_rollover_id(*,campaign_id,previous_market_date,previous_official_run_id,target_market_date,target_official_run_id,action):
    payload={"campaign_id":campaign_id,"previous_market_date":previous_market_date.isoformat(),"previous_official_run_id":previous_official_run_id,"target_market_date":target_market_date.isoformat(),"target_official_run_id":target_official_run_id,"action":Task9CampaignRolloverAction(action).value}
    return "task9-rollover-"+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
@dataclass(frozen=True,slots=True)
class Task9CampaignRolloverDecisionV1:
    campaign_id:str; action:Task9CampaignRolloverAction; previous_market_date:date; previous_official_run_id:str; target_market_date:date; target_official_run_id:str|None; reason_code:str
    def __post_init__(self):
        for n in ("campaign_id","previous_official_run_id","reason_code"): object.__setattr__(self,n,_text(getattr(self,n),n))
        object.__setattr__(self,"action",Task9CampaignRolloverAction(self.action))
        if type(self.previous_market_date) is not date or type(self.target_market_date) is not date or self.target_market_date<self.previous_market_date: raise ValueError("market date")
        if self.target_official_run_id is not None: object.__setattr__(self,"target_official_run_id",_text(self.target_official_run_id,"target_official_run_id"))
        if self.action in _NEW and self.target_official_run_id is None: raise ValueError("target_official_run_id")
    @property
    def rollover_id(self): return derive_task9_campaign_rollover_id(campaign_id=self.campaign_id,previous_market_date=self.previous_market_date,previous_official_run_id=self.previous_official_run_id,target_market_date=self.target_market_date,target_official_run_id=self.target_official_run_id,action=self.action)
@dataclass(frozen=True,slots=True)
class Task9CampaignRolloverReceiptV1:
    rollover_id:str; campaign_id:str; previous_market_date:date; previous_official_run_id:str; target_market_date:date; target_official_run_id:str|None; action:Task9CampaignRolloverAction; status:Task9CampaignRolloverReceiptStatus; runtime_config_snapshot_id:str; runtime_config_sha256:str; decision_reason:str; applied_at:datetime
    def __post_init__(self):
        for n in ("rollover_id","campaign_id","previous_official_run_id","runtime_config_snapshot_id","runtime_config_sha256","decision_reason"): object.__setattr__(self,n,_text(getattr(self,n),n))
        object.__setattr__(self,"action",Task9CampaignRolloverAction(self.action)); object.__setattr__(self,"status",Task9CampaignRolloverReceiptStatus(self.status))
        if type(self.previous_market_date) is not date or type(self.target_market_date) is not date or self.target_market_date<self.previous_market_date: raise ValueError("receipt market date")
        if self.target_official_run_id is not None: object.__setattr__(self,"target_official_run_id",_text(self.target_official_run_id,"target_official_run_id"))
        expected=derive_task9_campaign_rollover_id(campaign_id=self.campaign_id,previous_market_date=self.previous_market_date,previous_official_run_id=self.previous_official_run_id,target_market_date=self.target_market_date,target_official_run_id=self.target_official_run_id,action=self.action)
        if self.rollover_id!=expected: raise ValueError("rollover_id does not match immutable transition")
        if not isinstance(self.applied_at,datetime) or self.applied_at.tzinfo is None or self.applied_at.utcoffset() is None: raise ValueError("applied_at")
        object.__setattr__(self,"applied_at",self.applied_at.astimezone(timezone.utc))
    def immutable_identity(self): return (self.rollover_id,self.campaign_id,self.previous_market_date,self.previous_official_run_id,self.target_market_date,self.target_official_run_id,self.action,self.runtime_config_snapshot_id,self.runtime_config_sha256,self.decision_reason)
    def to_dict(self): return {"rollover_id":self.rollover_id,"campaign_id":self.campaign_id,"previous_market_date":self.previous_market_date.isoformat(),"previous_official_run_id":self.previous_official_run_id,"target_market_date":self.target_market_date.isoformat(),"target_official_run_id":self.target_official_run_id,"action":self.action.value,"status":self.status.value,"runtime_config_snapshot_id":self.runtime_config_snapshot_id,"runtime_config_sha256":self.runtime_config_sha256,"decision_reason":self.decision_reason,"applied_at":self.applied_at.isoformat()}
    @classmethod
    def from_dict(cls,v):
        try:
            d=dict(v); d["previous_market_date"]=date.fromisoformat(d["previous_market_date"]); d["target_market_date"]=date.fromisoformat(d["target_market_date"]); d["applied_at"]=datetime.fromisoformat(d["applied_at"]); return cls(**d)
        except (KeyError,TypeError,ValueError) as exc: raise ValueError("invalid rollover receipt") from exc
