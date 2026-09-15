"""Immutable, non-secret Task 9 provider capability/readiness authority."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from services.contracts.task9_runtime_config_v1 import ProviderFeatureStateV1
from services.contracts.task9_startup_failure_semantics_v1 import Task9StartupSemantic

class Task9ProviderFamily(str, Enum):
 ANGEL_AUTH_SESSION="ANGEL_AUTH_SESSION"; ANGEL_SPOT="ANGEL_SPOT"; ANGEL_OPTION_FULL="ANGEL_OPTION_FULL"; ANGEL_OPTION_GREEKS="ANGEL_OPTION_GREEKS"; ANGEL_INSTRUMENT_MASTER="ANGEL_INSTRUMENT_MASTER"; ANGEL_MARKET_WEBSOCKET="ANGEL_MARKET_WEBSOCKET"; INDIA_VIX="INDIA_VIX"; MARKET_BREADTH="MARKET_BREADTH"; INSTITUTIONAL_FLOW="INSTITUTIONAL_FLOW"; ECONOMIC_EVENT_CALENDAR="ECONOMIC_EVENT_CALENDAR"; GLOBAL_MARKET_DATA="GLOBAL_MARKET_DATA"; STRUCTURED_NEWS="STRUCTURED_NEWS"; LLM_CLASSIFIER="LLM_CLASSIFIER"
class Task9ProviderCapability(str, Enum):
 AUTH_SESSION="AUTH_SESSION"; SPOT_QUOTES="SPOT_QUOTES"; OPTION_FULL_QUOTES="OPTION_FULL_QUOTES"; OPTION_GREEKS="OPTION_GREEKS"; INSTRUMENT_MASTER="INSTRUMENT_MASTER"; MARKET_DATA_WEBSOCKET="MARKET_DATA_WEBSOCKET"; INDIA_VIX="INDIA_VIX"; EXTERNAL_CONTEXT="EXTERNAL_CONTEXT"; CLASSIFICATION="CLASSIFICATION"; PROVIDER_NATIVE_OI_CHANGE="PROVIDER_NATIVE_OI_CHANGE"; TASK9_DERIVED_OI_CHANGE="TASK9_DERIVED_OI_CHANGE"
class Task9ProviderReadinessStatus(str, Enum):
 READY="READY"; READY_PENDING_LIVE_PROOF="READY_PENDING_LIVE_PROOF"; UNAVAILABLE_OPTIONAL="UNAVAILABLE_OPTIONAL"; PROVIDER_NOT_SELECTED="PROVIDER_NOT_SELECTED"; DISABLED="DISABLED"; UNSUPPORTED="UNSUPPORTED"; BLOCKED_RETRYABLE="BLOCKED_RETRYABLE"; FAILED_FATAL="FAILED_FATAL"; NOT_APPLICABLE="NOT_APPLICABLE"
class Task9ProviderSupportStatus(str, Enum): DOCUMENTED="DOCUMENTED"; IMPLEMENTED="IMPLEMENTED"; UNSUPPORTED="UNSUPPORTED"; NOT_SELECTED="NOT_SELECTED"; UNKNOWN="UNKNOWN"
class Task9LiveProofStatus(str, Enum): PROVEN="PROVEN"; PENDING="PENDING"; NOT_APPLICABLE="NOT_APPLICABLE"
_SECRET=("secret","password","token","jwt","refresh","totp","authorization","api_key","client_id","pin")
def _text(v,n):
 if type(v)is not str or not(v:=v.strip()) or any(x in v.lower() for x in _SECRET):raise ValueError(n)
 return v
def _refs(v,n):
 if not isinstance(v,tuple) or any(type(x)is not str or not _text(x,n) for x in v) or len(set(v))!=len(v):raise ValueError(n)
 return v
@dataclass(frozen=True,slots=True)
class Task9ProviderCapabilityStateV1:
 provider_family:Task9ProviderFamily; capability:Task9ProviderCapability; market:str|None; exchange:str|None; required:bool; feature_intent:ProviderFeatureStateV1; documentation_status:Task9ProviderSupportStatus; implementation_status:Task9ProviderSupportStatus; live_proof_status:Task9LiveProofStatus; readiness_status:Task9ProviderReadinessStatus; startup_semantic:Task9StartupSemantic|None; freshness_policy_ref:str|None=None; rate_limit_policy_ref:str|None=None; evidence_refs:tuple[str,...]=(); incident_refs:tuple[str,...]=(); metadata:Mapping[str,object]=field(default_factory=dict)
 def __post_init__(self):
  try:
   for n,t in (("provider_family",Task9ProviderFamily),("capability",Task9ProviderCapability),("feature_intent",ProviderFeatureStateV1),("documentation_status",Task9ProviderSupportStatus),("implementation_status",Task9ProviderSupportStatus),("live_proof_status",Task9LiveProofStatus),("readiness_status",Task9ProviderReadinessStatus)):object.__setattr__(self,n,t(getattr(self,n)))
   if self.startup_semantic is not None:object.__setattr__(self,"startup_semantic",Task9StartupSemantic(self.startup_semantic))
  except (TypeError,ValueError) as e:raise ValueError("provider capability state") from e
  if type(self.required)is not bool:raise TypeError("required")
  if (self.market is None)!=(self.exchange is None):raise ValueError("market/exchange")
  if self.market is not None:object.__setattr__(self,"market",_text(self.market,"market").upper());object.__setattr__(self,"exchange",_text(self.exchange,"exchange").upper())
  for n in ("freshness_policy_ref","rate_limit_policy_ref"):
   v=getattr(self,n)
   if v is not None:object.__setattr__(self,n,_text(v,n))
  object.__setattr__(self,"evidence_refs",_refs(self.evidence_refs,"evidence_refs"));object.__setattr__(self,"incident_refs",_refs(self.incident_refs,"incident_refs"))
  if not isinstance(self.metadata,Mapping) or any(type(k)is not str or any(s in k.lower() for s in _SECRET) or type(v) not in {str,int,float,bool} or (type(v)is str and any(s in v.lower() for s in _SECRET)) for k,v in self.metadata.items()):raise ValueError("metadata")
  object.__setattr__(self,"metadata",MappingProxyType(dict(sorted(self.metadata.items()))))
  if self.readiness_status is Task9ProviderReadinessStatus.READY and self.live_proof_status is not Task9LiveProofStatus.PROVEN:raise ValueError("ready requires live proof")
  if self.readiness_status is Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED and self.feature_intent is not ProviderFeatureStateV1.PROVIDER_NOT_SELECTED:raise ValueError("provider intent")
  if self.readiness_status is Task9ProviderReadinessStatus.DISABLED and self.feature_intent not in {ProviderFeatureStateV1.DISABLED,ProviderFeatureStateV1.OPTIONAL_FUTURE}:raise ValueError("provider intent")
  if self.required and self.readiness_status in {Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL,Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED,Task9ProviderReadinessStatus.DISABLED,Task9ProviderReadinessStatus.NOT_APPLICABLE}:raise ValueError("required readiness")
 def to_dict(self):return {"provider_family":self.provider_family.value,"capability":self.capability.value,"market":self.market,"exchange":self.exchange,"required":self.required,"feature_intent":self.feature_intent.value,"documentation_status":self.documentation_status.value,"implementation_status":self.implementation_status.value,"live_proof_status":self.live_proof_status.value,"readiness_status":self.readiness_status.value,"startup_semantic":None if self.startup_semantic is None else self.startup_semantic.value,"freshness_policy_ref":self.freshness_policy_ref,"rate_limit_policy_ref":self.rate_limit_policy_ref,"evidence_refs":list(self.evidence_refs),"incident_refs":list(self.incident_refs),"metadata":dict(self.metadata)}
@dataclass(frozen=True,slots=True)
class Task9ProviderCapabilityReportV1:
 runtime_config_id:str;runtime_config_version:str; capability_states:tuple[Task9ProviderCapabilityStateV1,...];schema_version:str="task9_provider_capability_report.v1"
 def __post_init__(self):
  if self.schema_version!="task9_provider_capability_report.v1":raise ValueError("schema_version")
  object.__setattr__(self,"runtime_config_id",_text(self.runtime_config_id,"runtime_config_id"));object.__setattr__(self,"runtime_config_version",_text(self.runtime_config_version,"runtime_config_version"))
  if not isinstance(self.capability_states,tuple) or any(type(x)is not Task9ProviderCapabilityStateV1 for x in self.capability_states):raise ValueError("capability_states")
  ids=tuple((x.provider_family,x.capability,x.market,x.exchange) for x in self.capability_states)
  if len(set(ids))!=len(ids):raise ValueError("duplicate capability identity")
  object.__setattr__(self,"capability_states",tuple(sorted(self.capability_states,key=lambda x:(x.provider_family.value,x.capability.value,x.market or "",x.exchange or ""))))
 def to_dict(self):return {"schema_version":self.schema_version,"runtime_config_id":self.runtime_config_id,"runtime_config_version":self.runtime_config_version,"capability_states":[x.to_dict() for x in self.capability_states]}
 @classmethod
 def from_dict(cls,v):
  if not isinstance(v,Mapping):raise TypeError("report")
  d=dict(v)
  try:d["capability_states"]=tuple(Task9ProviderCapabilityStateV1(**{**x,"evidence_refs":tuple(x["evidence_refs"]),"incident_refs":tuple(x["incident_refs"])}) for x in d["capability_states"])
  except (KeyError,TypeError,ValueError) as e:raise ValueError("report serialization") from e
  return cls(**d)
