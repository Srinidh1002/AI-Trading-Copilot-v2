"""Immutable Task 9 campaign identity and active-pointer contracts."""
from __future__ import annotations
import re
from dataclasses import dataclass,field
from datetime import date,datetime,timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any,Mapping
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification
from services.contracts.task9_runtime_config_snapshot_v1 import validate_task9_runtime_config_snapshot_reference
class Task9CampaignStatus(str,Enum): ACTIVE="ACTIVE";PAUSED="PAUSED";COMPLETED="COMPLETED";HALTED="HALTED";INVALID="INVALID"
class Task9ActiveCampaignPointerStatus(str,Enum): ACTIVE="ACTIVE";PAUSED="PAUSED";COMPLETED="COMPLETED";HALTED="HALTED"
_SECRET=re.compile(r"secret|password|token|jwt|refresh|totp|authorization|api[_-]?key|client[_-]?id|\bpin\b",re.I)
def _text(v,n):
 if type(v)is not str or not(v:=v.strip()) or _SECRET.search(v):raise ValueError(n)
 return v
def _path(v,n):return Path(_text(v,n)).as_posix()
def _utc(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:raise ValueError(n)
 return v.astimezone(timezone.utc)
def _meta(v):
 if not isinstance(v,Mapping) or any(type(k)is not str or _SECRET.search(k) or type(x)not in {str,int,float,bool} or (type(x)is str and _SECRET.search(x)) for k,x in v.items()):raise ValueError("metadata")
 return MappingProxyType(dict(sorted(v.items())))
@dataclass(frozen=True,slots=True)
class Task9CampaignManifestV1:
 campaign_id:str;campaign_version:str;campaign_status:Task9CampaignStatus;created_market_date:date;registry_root:str;campaign_root:str;runtime_config_snapshot_id:str;runtime_config_sha256:str;canonical_policy_references:Mapping[str,str]=field(default_factory=dict);notes:tuple[str,...]=();metadata:Mapping[str,object]=field(default_factory=dict);target_nifty_count:int=100;target_sensex_count:int=100;official_certification_only:bool=True;replay_counts_toward_target:bool=False;diagnostic_counts_toward_target:bool=False;wait_counts_toward_target:bool=False;no_trade_counts_toward_target:bool=False;execution_mode:str="PAPER";broker_order_submission:bool=False;live_execution_eligible:bool=False;schema_version:str="task9_campaign_manifest.v1"
 def __post_init__(self):
  if self.schema_version!="task9_campaign_manifest.v1":raise ValueError("schema_version")
  for n in ("campaign_id","campaign_version"):object.__setattr__(self,n,_text(getattr(self,n),n))
  for n in ("registry_root","campaign_root"):object.__setattr__(self,n,_path(getattr(self,n),n))
  if type(self.created_market_date)is not date:raise ValueError("created_market_date")
  validate_task9_runtime_config_snapshot_reference(self.runtime_config_snapshot_id,self.runtime_config_sha256)
  if self.target_nifty_count!=100 or self.target_sensex_count!=100:raise ValueError("certification targets")
  if not self.official_certification_only or any((self.replay_counts_toward_target,self.diagnostic_counts_toward_target,self.wait_counts_toward_target,self.no_trade_counts_toward_target)):raise ValueError("countability invariants")
  if self.execution_mode!="PAPER" or self.broker_order_submission is not False or self.live_execution_eligible is not False:raise ValueError("PAPER")
  object.__setattr__(self,"campaign_status",Task9CampaignStatus(self.campaign_status));object.__setattr__(self,"canonical_policy_references",MappingProxyType(dict(sorted((_text(k,"policy key"),_text(v,"policy ref")) for k,v in self.canonical_policy_references.items()))));object.__setattr__(self,"notes",tuple(_text(x,"note") for x in self.notes));object.__setattr__(self,"metadata",_meta(self.metadata))
 def numeric_target_met(self,*,nifty_count:int,sensex_count:int)->bool:
  if type(nifty_count)is not int or type(sensex_count)is not int or nifty_count<0 or sensex_count<0:raise ValueError("counts")
  return nifty_count>=100 and sensex_count>=100
 def to_dict(self):
  return {n:(self.created_market_date.isoformat() if n=="created_market_date" else dict(self.canonical_policy_references) if n=="canonical_policy_references" else list(self.notes) if n=="notes" else dict(self.metadata) if n=="metadata" else getattr(self,n).value if n=="campaign_status" else getattr(self,n)) for n in self.__dataclass_fields__}
 @classmethod
 def from_dict(cls,v):
  d=dict(v);d["created_market_date"]=date.fromisoformat(d["created_market_date"]);d["notes"]=tuple(d["notes"]);return cls(**d)
@dataclass(frozen=True,slots=True)
class Task9ActiveCampaignPointerV1:
 campaign_id:str;campaign_manifest_ref:str;campaign_root:str;registry_root:str;active_market_date:date;active_official_run_id:str;run_classification:str;runtime_config_snapshot_id:str;runtime_config_sha256:str;updated_at:datetime;status:Task9ActiveCampaignPointerStatus;startup_preflight_id:str|None=None;schema_version:str="task9_active_campaign_pointer.v1"
 def __post_init__(self):
  if self.schema_version!="task9_active_campaign_pointer.v1":raise ValueError("schema_version")
  for n in ("campaign_id","campaign_manifest_ref","active_official_run_id"):object.__setattr__(self,n,_text(getattr(self,n),n))
  for n in ("campaign_root","registry_root"):object.__setattr__(self,n,_path(getattr(self,n),n))
  if type(self.active_market_date)is not date:raise ValueError("active_market_date")
  if validate_task9_run_classification(self.run_classification)!="OFFICIAL_CERTIFICATION":raise ValueError("active pointer requires official run")
  object.__setattr__(self,"run_classification","OFFICIAL_CERTIFICATION");validate_task9_runtime_config_snapshot_reference(self.runtime_config_snapshot_id,self.runtime_config_sha256);object.__setattr__(self,"updated_at",_utc(self.updated_at,"updated_at"));object.__setattr__(self,"status",Task9ActiveCampaignPointerStatus(self.status))
  if self.startup_preflight_id is not None:object.__setattr__(self,"startup_preflight_id",_text(self.startup_preflight_id,"startup_preflight_id"))
 def to_dict(self):return {n:(self.active_market_date.isoformat() if n=="active_market_date" else self.updated_at.isoformat() if n=="updated_at" else self.status.value if n=="status" else getattr(self,n)) for n in self.__dataclass_fields__}
 @classmethod
 def from_dict(cls,v):
  d=dict(v);d["active_market_date"]=date.fromisoformat(d["active_market_date"]);d["updated_at"]=datetime.fromisoformat(d["updated_at"]);return cls(**d)
