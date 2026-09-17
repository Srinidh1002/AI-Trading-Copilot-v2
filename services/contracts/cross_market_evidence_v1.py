"""Immutable supplied cross-market relationship evidence; no calculation."""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity

_PAIRS = {
    (("NIFTY", "NSE"), ("SENSEX", "BSE")): "BROAD_MARKET",
    (("SENSEX", "BSE"), ("NIFTY", "NSE")): "BROAD_MARKET",
    (("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE")): "FINANCIAL_INDEX",
    (("FINNIFTY", "NSE"), ("BANKNIFTY", "NSE")): "FINANCIAL_INDEX",
}
_STATES = {"STRONG_POSITIVE", "MODERATE_POSITIVE", "WEAK", "MODERATE_NEGATIVE", "STRONG_NEGATIVE", "UNAVAILABLE"}
_DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE"}
_CONFIRMATION = {"CONFIRMING", "PARTIAL", "NOT_CONFIRMING", "UNAVAILABLE"}
_DIVERGENCE = {"NONE", "POSITIVE_DIVERGENCE", "NEGATIVE_DIVERGENCE", "DIRECTIONAL_DIVERGENCE", "UNAVAILABLE"}
_STATUSES = {"READY", "READY_WITH_WARNINGS", "INSUFFICIENT_DATA", "STALE", "MISALIGNED", "UNAVAILABLE", "BLOCKED"}
_BLOCKED = _STATUSES - {"READY", "READY_WITH_WARNINGS"}

def _text(value: object, name: str, *, upper: bool = False) -> str:
    if not isinstance(value, str): raise TypeError(f"{name} must be a string")
    value = value.strip()
    if not value: raise ValueError(f"{name} must not be empty")
    return value.upper() if upper else value
def _time(value: object, name: str) -> datetime:
    if not isinstance(value, datetime): raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None: raise ValueError(f"{name} must be timezone-aware")
    return value
def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple): raise TypeError(f"{name} must be a tuple")
    result=tuple(_text(x, f"{name} item") for x in value)
    if len(set(result)) != len(result): raise ValueError(f"{name} must not contain duplicates")
    return result
def _metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise TypeError("metadata must be a mapping")
    try: payload=json.loads(json.dumps(dict(value), sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc: raise ValueError("metadata must be JSON-safe") from exc
    return MappingProxyType(payload)

@dataclass(frozen=True, slots=True)
class CrossMarketEvidenceV1:
    cross_market_evidence_id: str; created_at: datetime
    primary_symbol: str; primary_exchange: str; related_symbol: str; related_exchange: str
    relationship_type: str; timeframe: str; lookback_observations: int; aligned_sample_size: int
    correlation_value: float | None; correlation_strength: float; correlation_state: str
    primary_direction: str; related_direction: str; confirmation_state: str; divergence_state: str
    evidence_status: str; primary_source_id: str; related_source_id: str
    primary_source_timestamp: datetime; related_source_timestamp: datetime
    blockers: tuple[str, ...] = (); warnings: tuple[str, ...] = (); metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"; live_execution_eligible: bool = False; schema_version: str = "cross_market_evidence.v1"
    def __post_init__(self) -> None:
        for name in ("cross_market_evidence_id","timeframe","primary_source_id","related_source_id"):
            object.__setattr__(self,name,_text(getattr(self,name),name))
        object.__setattr__(self,"created_at",_time(self.created_at,"created_at"))
        for name in ("primary_source_timestamp","related_source_timestamp"): object.__setattr__(self,name,_time(getattr(self,name),name))
        p=normalize_market_identity(self.primary_symbol,self.primary_exchange); r=normalize_market_identity(self.related_symbol,self.related_exchange)
        if p is None or r is None: raise ValueError("unsupported market identity")
        if p == r or (p,r) not in _PAIRS: raise ValueError("unsupported cross-market relationship")
        object.__setattr__(self,"primary_symbol",p[0]); object.__setattr__(self,"primary_exchange",p[1]); object.__setattr__(self,"related_symbol",r[0]); object.__setattr__(self,"related_exchange",r[1])
        relation=_text(self.relationship_type,"relationship_type",upper=True)
        if relation != _PAIRS[p,r]: raise ValueError("relationship_type does not match canonical relationship")
        object.__setattr__(self,"relationship_type",relation)
        for name, allowed in (("correlation_state",_STATES),("primary_direction",_DIRECTIONS),("related_direction",_DIRECTIONS),("confirmation_state",_CONFIRMATION),("divergence_state",_DIVERGENCE),("evidence_status",_STATUSES)):
            value=_text(getattr(self,name),name,upper=True)
            if value not in allowed: raise ValueError(f"unsupported {name}")
            object.__setattr__(self,name,value)
        for name in ("lookback_observations","aligned_sample_size"):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,int): raise TypeError(f"{name} must be an integer")
            if value < 0: raise ValueError(f"{name} must be non-negative")
        if self.aligned_sample_size > self.lookback_observations: raise ValueError("aligned_sample_size cannot exceed lookback_observations")
        if isinstance(self.correlation_strength,bool) or not isinstance(self.correlation_strength,(int,float)): raise TypeError("correlation_strength must be numeric")
        strength=float(self.correlation_strength)
        if not math.isfinite(strength) or not 0 <= strength <= 1: raise ValueError("correlation_strength must be between zero and one")
        object.__setattr__(self,"correlation_strength",strength)
        value=self.correlation_value
        if value is not None:
            if isinstance(value,bool) or not isinstance(value,(int,float)): raise TypeError("correlation_value must be numeric or None")
            value=float(value)
            if not math.isfinite(value) or not -1 <= value <= 1: raise ValueError("correlation_value must be between -1 and one")
        object.__setattr__(self,"correlation_value",value)
        object.__setattr__(self,"blockers",_messages(self.blockers,"blockers")); object.__setattr__(self,"warnings",_messages(self.warnings,"warnings")); object.__setattr__(self,"metadata",_metadata(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "cross_market_evidence.v1": raise ValueError("cross-market evidence is paper-only v1")
        if self.evidence_status == "READY" and (self.blockers or self.warnings or value is None or not self.aligned_sample_size or self.correlation_state == "UNAVAILABLE"): raise ValueError("READY evidence is contradictory")
        if self.evidence_status == "READY_WITH_WARNINGS" and (self.blockers or not self.warnings or value is None or not self.aligned_sample_size or self.correlation_state == "UNAVAILABLE"): raise ValueError("READY_WITH_WARNINGS evidence is contradictory")
        if self.evidence_status in _BLOCKED and (not self.blockers or value is not None or strength != 0 or self.correlation_state != "UNAVAILABLE" or self.confirmation_state != "UNAVAILABLE" or self.divergence_state != "UNAVAILABLE"): raise ValueError("unavailable evidence must be explicit and blocked")
    def to_dict(self) -> dict[str, Any]:
        return {**{n:getattr(self,n) for n in ("schema_version","cross_market_evidence_id","primary_symbol","primary_exchange","related_symbol","related_exchange","relationship_type","timeframe","lookback_observations","aligned_sample_size","correlation_value","correlation_strength","correlation_state","primary_direction","related_direction","confirmation_state","divergence_state","evidence_status","primary_source_id","related_source_id","execution_mode","live_execution_eligible")}, "created_at":self.created_at.isoformat(),"primary_source_timestamp":self.primary_source_timestamp.isoformat(),"related_source_timestamp":self.related_source_timestamp.isoformat(),"blockers":list(self.blockers),"warnings":list(self.warnings),"metadata":dict(self.metadata)}
    def to_json(self) -> str: return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self) -> dict[str, Any]:
        value=self.to_dict(); value.pop("cross_market_evidence_id"); value.pop("created_at"); return value
