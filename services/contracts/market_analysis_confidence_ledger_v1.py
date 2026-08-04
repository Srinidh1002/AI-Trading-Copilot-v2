"""PAPER-only deterministic shadow confidence ledger contracts."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

_IDENTITIES = frozenset({("NIFTY", "NSE"), ("SENSEX", "BSE")})
_TYPES = frozenset({"DIRECTIONAL", "QUALITY", "CONTRADICTION", "SUITABILITY", "INFORMATIONAL"})
_DIRECTIONS = frozenset({"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE", "CONFLICTING"})
_STATUSES = frozenset({"READY", "UNAVAILABLE", "BLOCKED", "CONFLICTING"})
_FORBIDDEN = frozenset({"api_key", "apikey", "secret", "password", "pin", "authorization", "access_token", "refresh_token", "jwt", "raw_payload", "provider_payload", "raw_exception", "exception_text"})

def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (clean := value.strip()): raise ValueError(name)
    return clean
def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None: raise ValueError(name)
    return value
def _number(value: object, name: str, low: float = -100.0, high: float = 100.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(float(value)) or not low <= float(value) <= high: raise ValueError(name)
    return float(value)
def _messages(value: object, name: str) -> tuple[str,...]:
    if not isinstance(value, tuple): raise TypeError(name)
    result = tuple(_text(item,name) for item in value)
    if len(set(result)) != len(result): raise ValueError(name)
    return result
def _metadata(value: object) -> Mapping[str,Any]:
    if not isinstance(value, Mapping): raise TypeError("metadata")
    copied = dict(value)
    def safe(item: object) -> bool:
        if isinstance(item,Mapping): return all(isinstance(k,str) and k.lower() not in _FORBIDDEN and safe(v) for k,v in item.items())
        if isinstance(item,(tuple,list)): return all(safe(v) for v in item)
        return True
    if not safe(copied): raise ValueError("unsafe metadata")
    try: json.dumps(copied,sort_keys=True,allow_nan=False)
    except (TypeError,ValueError) as exc: raise ValueError("metadata") from exc
    return MappingProxyType(copied)

@dataclass(frozen=True, slots=True)
class MarketAnalysisConfidenceEntryV1:
    entry_id:str; entry_type:str; source_component:str; source_result_id:str|None; pillar_name:str|None
    underlying_symbol:str; exchange:str; cycle_id:str; observation_id:str; direction:str
    raw_value:float|None; normalized_value:float|None; weight:float; weighted_value:float; adjustment_value:float
    counted:bool; exclusion_reason:str|None; source_timestamp:datetime|None; evaluated_at:datetime
    blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="market_analysis_confidence_entry.v1"
    def __post_init__(self):
        for name in ("entry_id","source_component","cycle_id","observation_id"): object.__setattr__(self,name,_text(getattr(self,name),name))
        identity=(_text(self.underlying_symbol,"underlying_symbol").upper(),_text(self.exchange,"exchange").upper())
        if identity not in _IDENTITIES: raise ValueError("market identity")
        object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1])
        entry_type=_text(self.entry_type,"entry_type").upper(); direction=_text(self.direction,"direction").upper()
        if entry_type not in _TYPES or direction not in _DIRECTIONS or not isinstance(self.counted,bool): raise ValueError("controlled vocabulary")
        if self.counted != (self.exclusion_reason is None): raise ValueError("counted/exclusion coherence")
        object.__setattr__(self,"entry_type",entry_type);object.__setattr__(self,"direction",direction)
        if self.pillar_name is not None: object.__setattr__(self,"pillar_name",_text(self.pillar_name,"pillar_name"))
        if self.source_result_id is not None: object.__setattr__(self,"source_result_id",_text(self.source_result_id,"source_result_id"))
        if self.exclusion_reason is not None: object.__setattr__(self,"exclusion_reason",_text(self.exclusion_reason,"exclusion_reason").upper())
        for name in ("raw_value","normalized_value"):
            value=getattr(self,name)
            if value is not None: object.__setattr__(self,name,_number(value,name))
        if self.normalized_value is not None and not 0.0 <= self.normalized_value <= 1.0: raise ValueError("normalized_value")
        for name in ("weight","weighted_value","adjustment_value"): object.__setattr__(self,name,_number(getattr(self,name),name))
        if self.source_timestamp is not None: _aware(self.source_timestamp,"source_timestamp")
        _aware(self.evaluated_at,"evaluated_at")
        if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_analysis_confidence_entry.v1": raise ValueError("PAPER-only entry")
        object.__setattr__(self,"blockers",_messages(self.blockers,"blockers"));object.__setattr__(self,"warnings",_messages(self.warnings,"warnings"));object.__setattr__(self,"metadata",_metadata(self.metadata))
    def to_dict(self):
        return {"entry_id":self.entry_id,"entry_type":self.entry_type,"source_component":self.source_component,"source_result_id":self.source_result_id,"pillar_name":self.pillar_name,"direction":self.direction,"raw_value":self.raw_value,"normalized_value":self.normalized_value,"weight":self.weight,"weighted_value":self.weighted_value,"adjustment_value":self.adjustment_value,"counted":self.counted,"exclusion_reason":self.exclusion_reason,"source_timestamp":self.source_timestamp.isoformat() if self.source_timestamp else None,"evaluated_at":self.evaluated_at.isoformat(),"blockers":list(self.blockers),"warnings":list(self.warnings),"metadata":dict(self.metadata)}

@dataclass(frozen=True, slots=True)
class MarketAnalysisConfidenceLedgerV1:
    ledger_id:str; underlying_symbol:str; exchange:str; cycle_id:str; observation_id:str; evaluated_at:datetime
    base_score:float; base_confidence:float; bullish_total:float; bearish_total:float; neutral_total:float; quality_penalty_total:float; contradiction_penalty_total:float; suitability_penalty_total:float; final_score:float; final_confidence:float; provisional_direction:str; status:str; entries:tuple[MarketAnalysisConfidenceEntryV1,...]
    blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); policy_version:str="market_analysis_confidence_policy.v1.shadow"; execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="market_analysis_confidence_ledger.v1"
    def __post_init__(self):
        for name in ("ledger_id","cycle_id","observation_id","policy_version"): object.__setattr__(self,name,_text(getattr(self,name),name))
        identity=(_text(self.underlying_symbol,"underlying_symbol").upper(),_text(self.exchange,"exchange").upper())
        if identity not in _IDENTITIES: raise ValueError("market identity")
        object.__setattr__(self,"underlying_symbol",identity[0]);object.__setattr__(self,"exchange",identity[1]);_aware(self.evaluated_at,"evaluated_at")
        direction=_text(self.provisional_direction,"provisional_direction").upper(); status=_text(self.status,"status").upper()
        if direction not in _DIRECTIONS or status not in _STATUSES: raise ValueError("ledger vocabulary")
        object.__setattr__(self,"provisional_direction",direction);object.__setattr__(self,"status",status)
        for name in ("base_score","base_confidence","bullish_total","bearish_total","neutral_total","quality_penalty_total","contradiction_penalty_total","suitability_penalty_total","final_score","final_confidence"): object.__setattr__(self,name,_number(getattr(self,name),name,0.0,100.0))
        if not isinstance(self.entries,tuple) or tuple(sorted(item.entry_id for item in self.entries)) != tuple(item.entry_id for item in self.entries): raise ValueError("deterministic entries")
        if any(type(item) is not MarketAnalysisConfidenceEntryV1 or (item.underlying_symbol,item.exchange,item.cycle_id,item.observation_id,item.evaluated_at)!=(identity[0],identity[1],self.cycle_id,self.observation_id,self.evaluated_at) for item in self.entries): raise ValueError("entry coherence")
        if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_analysis_confidence_ledger.v1": raise ValueError("PAPER-only ledger")
        object.__setattr__(self,"blockers",_messages(self.blockers,"blockers"));object.__setattr__(self,"warnings",_messages(self.warnings,"warnings"))
    def to_dict(self):
        return {"ledger_id":self.ledger_id,"underlying_symbol":self.underlying_symbol,"exchange":self.exchange,"cycle_id":self.cycle_id,"observation_id":self.observation_id,"evaluated_at":self.evaluated_at.isoformat(),"base_score":self.base_score,"base_confidence":self.base_confidence,"bullish_total":self.bullish_total,"bearish_total":self.bearish_total,"neutral_total":self.neutral_total,"quality_penalty_total":self.quality_penalty_total,"contradiction_penalty_total":self.contradiction_penalty_total,"suitability_penalty_total":self.suitability_penalty_total,"final_score":self.final_score,"final_confidence":self.final_confidence,"provisional_direction":self.provisional_direction,"status":self.status,"entries":[entry.to_dict() for entry in self.entries],"blockers":list(self.blockers),"warnings":list(self.warnings),"policy_version":self.policy_version,"execution_mode":self.execution_mode,"live_execution_eligible":self.live_execution_eligible,"schema_version":self.schema_version}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
