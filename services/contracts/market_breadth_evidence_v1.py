"""Immutable supplied market-breadth evidence; no constituent access."""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping
from services.core.market_identity import normalize_market_identity
_B={"BULLISH","BEARISH","NEUTRAL","UNAVAILABLE"}; _P={"BROAD","NARROW","BALANCED","UNAVAILABLE"}; _H={"CONFIRMS","CONTRADICTS","NEUTRAL","UNAVAILABLE"}; _S={"READY","READY_WITH_WARNINGS","INSUFFICIENT_DATA","STALE","UNAVAILABLE","BLOCKED"}; _X=_S-{"READY","READY_WITH_WARNINGS"}
def _t(v,n,u=False):
    if not isinstance(v,str): raise TypeError(f"{n} must be a string")
    v=v.strip()
    if not v: raise ValueError(f"{n} must not be empty")
    return v.upper() if u else v
def _dt(v,n):
    if not isinstance(v,datetime): raise TypeError(f"{n} must be a datetime")
    if v.tzinfo is None or v.utcoffset() is None: raise ValueError(f"{n} must be timezone-aware")
    return v
def _msgs(v,n):
    if not isinstance(v,tuple): raise TypeError(f"{n} must be a tuple")
    v=tuple(_t(x,f"{n} item") for x in v)
    if len(v)!=len(set(v)): raise ValueError(f"{n} must not contain duplicates")
    return v
def _meta(v):
    if not isinstance(v,Mapping): raise TypeError("metadata must be a mapping")
    try: return MappingProxyType(json.loads(json.dumps(dict(v),sort_keys=True,allow_nan=False)))
    except (TypeError,ValueError) as e: raise ValueError("metadata must be JSON-safe") from e
@dataclass(frozen=True,slots=True)
class MarketBreadthEvidenceV1:
    market_breadth_evidence_id:str; created_at:datetime; underlying_symbol:str; exchange:str; source_id:str; source_timestamp:datetime
    advance_count:int|None; decline_count:int|None; unchanged_count:int|None; total_count:int|None; covered_count:int; coverage_ratio:float; advance_decline_ratio:float|None
    breadth_bias:str; breadth_strength:float; participation_state:str; heavyweight_contribution_state:str; evidence_status:str
    blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); metadata:Mapping[str,Any]=field(default_factory=dict)
    execution_mode:str="PAPER"; live_execution_eligible:bool=False; schema_version:str="market_breadth_evidence.v1"
    def __post_init__(self):
        for n in ("market_breadth_evidence_id","source_id"): object.__setattr__(self,n,_t(getattr(self,n),n))
        object.__setattr__(self,"created_at",_dt(self.created_at,"created_at")); object.__setattr__(self,"source_timestamp",_dt(self.source_timestamp,"source_timestamp"))
        identity=normalize_market_identity(self.underlying_symbol,self.exchange)
        if identity is None: raise ValueError("unsupported market identity")
        object.__setattr__(self,"underlying_symbol",identity[0]); object.__setattr__(self,"exchange",identity[1])
        for n,a in (("breadth_bias",_B),("participation_state",_P),("heavyweight_contribution_state",_H),("evidence_status",_S)):
            v=_t(getattr(self,n),n,True)
            if v not in a: raise ValueError(f"unsupported {n}")
            object.__setattr__(self,n,v)
        counts=[]
        for n in ("advance_count","decline_count","unchanged_count","total_count"):
            v=getattr(self,n)
            if v is not None and (isinstance(v,bool) or not isinstance(v,int)): raise TypeError(f"{n} must be an integer or None")
            if v is not None and v<0: raise ValueError(f"{n} must be non-negative")
            counts.append(v)
        if any(v is None for v in counts) and any(v is not None for v in counts): raise ValueError("breadth counts must be complete or unavailable")
        if isinstance(self.covered_count,bool) or not isinstance(self.covered_count,int): raise TypeError("covered_count must be an integer")
        if self.covered_count<0: raise ValueError("covered_count must be non-negative")
        if counts[3] is not None and (sum(counts[:3]) != counts[3] or self.covered_count>counts[3]): raise ValueError("breadth counts are inconsistent")
        for n in ("coverage_ratio","breadth_strength"):
            v=getattr(self,n)
            if isinstance(v,bool) or not isinstance(v,(int,float)): raise TypeError(f"{n} must be numeric")
            v=float(v)
            if not math.isfinite(v) or not 0<=v<=1: raise ValueError(f"{n} must be between zero and one")
            object.__setattr__(self,n,v)
        ratio=self.advance_decline_ratio
        if ratio is not None:
            if isinstance(ratio,bool) or not isinstance(ratio,(int,float)): raise TypeError("advance_decline_ratio must be numeric or None")
            ratio=float(ratio)
            if not math.isfinite(ratio) or ratio<0: raise ValueError("advance_decline_ratio must be finite and non-negative")
        object.__setattr__(self,"advance_decline_ratio",ratio); object.__setattr__(self,"blockers",_msgs(self.blockers,"blockers")); object.__setattr__(self,"warnings",_msgs(self.warnings,"warnings")); object.__setattr__(self,"metadata",_meta(self.metadata))
        if counts[3] is not None:
            if not math.isclose(self.coverage_ratio, self.covered_count / counts[3], abs_tol=1e-12):
                raise ValueError("coverage_ratio does not match covered_count")
            if counts[1] == 0:
                if ratio is not None: raise ValueError("advance_decline_ratio must be unavailable when decline_count is zero")
            elif ratio is None or not math.isclose(ratio, counts[0] / counts[1], abs_tol=1e-12):
                raise ValueError("advance_decline_ratio does not match breadth counts")
        if self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.schema_version!="market_breadth_evidence.v1": raise ValueError("breadth evidence is paper-only v1")
        ready=self.evidence_status in {"READY","READY_WITH_WARNINGS"}
        if ready and (counts[3] is None or not self.covered_count or self.breadth_bias=="UNAVAILABLE" or self.breadth_strength==0 or self.blockers): raise ValueError("ready breadth requires complete available evidence")
        if self.evidence_status=="READY" and self.warnings: raise ValueError("READY breadth cannot contain warnings")
        if self.evidence_status=="READY_WITH_WARNINGS" and not self.warnings: raise ValueError("READY_WITH_WARNINGS breadth requires warnings")
        if self.evidence_status in _X and (not self.blockers or self.breadth_bias!="UNAVAILABLE" or self.breadth_strength!=0): raise ValueError("unavailable breadth must be explicit and blocked")
    def to_dict(self):
        d={n:getattr(self,n) for n in self.__dataclass_fields__ if n not in {"created_at","source_timestamp","blockers","warnings","metadata"}}; d["created_at"]=self.created_at.isoformat(); d["source_timestamp"]=self.source_timestamp.isoformat(); d["blockers"]=list(self.blockers); d["warnings"]=list(self.warnings); d["metadata"]=dict(self.metadata); return d
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self): d=self.to_dict(); d.pop("market_breadth_evidence_id"); d.pop("created_at"); return d
