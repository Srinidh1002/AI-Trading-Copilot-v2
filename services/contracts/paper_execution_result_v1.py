"""Immutable result of a single canonical paper-execution attempt."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES

_STATUSES={"ACCEPTED","FILLED","REJECTED","BLOCKED","DUPLICATE","FAILED"}; _MARKETS=SUPPORTED_MARKET_IDENTITIES
def _text(v,n):
    if not isinstance(v,str) or not v.strip(): raise ValueError(f"{n} is required.")
def _aware(v,n):
    if not isinstance(v,datetime) or v.tzinfo is None: raise ValueError(f"{n} must be timezone-aware.")
def _pos(v,n):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0: raise ValueError(f"{n} must be finite and positive.")
def _pos_int(v,n):
    if isinstance(v,bool) or not isinstance(v,int) or v<=0: raise ValueError(f"{n} must be a positive integer.")

@dataclass(frozen=True, slots=True)
class PaperExecutionResultV1:
    execution_result_id:str; execution_request_id:str; created_at:datetime; idempotency_key:str; execution_status:str
    authorization_id:str|None=None; paper_candidate_id:str|None=None; canonical_risk_result_id:str|None=None; trade_plan_id:str|None=None; sizing_result_id:str|None=None
    underlying_symbol:str|None=None; exchange:str|None=None; action:str|None=None; option_type:str|None=None; position_side:str|None=None; trading_symbol:str|None=None
    requested_quantity:int|None=None; filled_quantity:int|None=None; requested_lots:int|None=None; filled_lots:int|None=None; reference_price:float|None=None; fill_price:float|None=None; capital_used:float|None=None; realized_maximum_loss:float|None=None
    submitted_at:datetime|None=None; filled_at:datetime|None=None; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); schema_version:str="paper_execution_result.v1"; execution_mode:str="PAPER"; live_execution_eligible:bool=False
    def __post_init__(self):
        if self.schema_version!="paper_execution_result.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.execution_status not in _STATUSES: raise ValueError("Invalid paper execution result control values.")
        for n in ("execution_result_id","execution_request_id","idempotency_key"): _text(getattr(self,n),n)
        _aware(self.created_at,"created_at")
        if self.submitted_at is not None: _aware(self.submitted_at,"submitted_at")
        if self.filled_at is not None: _aware(self.filled_at,"filled_at")
        if self.filled_at and self.submitted_at and self.filled_at<self.submitted_at: raise ValueError("filled_at must not precede submitted_at.")
        blockers,warnings=tuple(self.blockers),tuple(self.warnings)
        if any(not isinstance(x,str) or not x for x in blockers+warnings): raise ValueError("blockers and warnings must contain non-empty strings.")
        object.__setattr__(self,"blockers",blockers); object.__setattr__(self,"warnings",warnings)
        if self.execution_status in {"REJECTED","BLOCKED","FAILED"} and not self.blockers: raise ValueError("Terminal rejection requires blockers.")
        if self.execution_status=="DUPLICATE" and not (self.blockers or self.warnings): raise ValueError("Duplicate requires an explanation.")
        fill=(self.filled_quantity,self.filled_lots,self.fill_price,self.capital_used,self.realized_maximum_loss,self.filled_at)
        if self.execution_status!="FILLED" and any(x is not None for x in fill): raise ValueError("Non-filled result cannot fabricate fill data.")
        if self.execution_status=="ACCEPTED":
            for n in ("authorization_id","paper_candidate_id","canonical_risk_result_id","trade_plan_id","sizing_result_id"): _text(getattr(self,n),n)
            if self.submitted_at is None or any(x is not None for x in (self.filled_quantity,self.filled_lots,self.fill_price,self.capital_used,self.realized_maximum_loss,self.filled_at)): raise ValueError("Accepted result requires complete linkage, submission, and no fills.")
        if self.execution_status=="FILLED":
            for n in ("authorization_id","paper_candidate_id","canonical_risk_result_id","trade_plan_id","sizing_result_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol"): _text(getattr(self,n),n)
            if (self.underlying_symbol,self.exchange) not in _MARKETS or (self.action,self.option_type) not in {("BUY","CALL"),("SELL","PUT")} or self.position_side!="LONG": raise ValueError("Filled result has invalid long-premium identity.")
            for n in ("requested_quantity","filled_quantity","requested_lots","filled_lots"): _pos_int(getattr(self,n),n)
            for n in ("reference_price","fill_price","capital_used","realized_maximum_loss"): _pos(getattr(self,n),n)
            if self.filled_quantity>self.requested_quantity or self.filled_lots>self.requested_lots or self.submitted_at is None or self.filled_at is None or self.blockers: raise ValueError("Invalid filled result.")
    def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self): value=self.to_dict(); value.pop("execution_result_id"); value.pop("created_at"); return value
