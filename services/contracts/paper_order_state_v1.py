"""Immutable state record for a future in-memory paper-order lifecycle."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES

_STATUSES={"CREATED","AUTHORIZED","SUBMITTED","FILLED","REJECTED","BLOCKED","CANCELLED","FAILED"}; _TERMINAL={"FILLED","REJECTED","BLOCKED","CANCELLED","FAILED"}
_NEXT={"CREATED":{"AUTHORIZED","BLOCKED","FAILED"},"AUTHORIZED":{"SUBMITTED","BLOCKED","FAILED"},"SUBMITTED":{"FILLED","REJECTED","CANCELLED","FAILED"}}
def _text(v,n):
    if not isinstance(v,str) or not v.strip(): raise ValueError(f"{n} is required.")
def _aware(v,n):
    if not isinstance(v,datetime) or v.tzinfo is None: raise ValueError(f"{n} must be timezone-aware.")
def _pos(v,n):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0: raise ValueError(f"{n} must be finite and positive.")
def _pos_int(v,n):
    if isinstance(v,bool) or not isinstance(v,int) or v<=0: raise ValueError(f"{n} must be a positive integer.")
@dataclass(frozen=True, slots=True)
class PaperOrderStateV1:
    paper_order_id:str; created_at:datetime; updated_at:datetime; order_status:str; execution_request_id:str; idempotency_key:str; underlying_symbol:str; exchange:str
    authorization_id:str|None=None; execution_result_id:str|None=None; paper_candidate_id:str|None=None; canonical_risk_result_id:str|None=None; trading_symbol:str|None=None; action:str|None=None; option_type:str|None=None; position_side:str|None=None
    quantity:int|None=None; lots:int|None=None; reference_price:float|None=None; fill_price:float|None=None; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); schema_version:str="paper_order_state.v1"; execution_mode:str="PAPER"; live_execution_eligible:bool=False
    def __post_init__(self):
        if self.schema_version!="paper_order_state.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.order_status not in _STATUSES: raise ValueError("Invalid paper order control values.")
        for n in ("paper_order_id","execution_request_id","idempotency_key"): _text(getattr(self,n),n)
        if (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES: raise ValueError("Unsupported paper order market identity.")
        _aware(self.created_at,"created_at"); _aware(self.updated_at,"updated_at")
        if self.updated_at<self.created_at: raise ValueError("updated_at must not precede created_at.")
        blockers,warnings=tuple(self.blockers),tuple(self.warnings)
        if any(not isinstance(x,str) or not x for x in blockers+warnings): raise ValueError("blockers and warnings must contain non-empty strings.")
        object.__setattr__(self,"blockers",blockers); object.__setattr__(self,"warnings",warnings)
        if self.order_status in {"REJECTED","BLOCKED","FAILED"} and not self.blockers: raise ValueError("Rejected state requires blockers.")
        if self.order_status=="CANCELLED" and not (self.blockers or self.warnings): raise ValueError("Cancelled state requires a reason.")
        if self.order_status!="FILLED" and self.fill_price is not None: raise ValueError("Non-filled order cannot have a fill price.")
        if self.order_status in {"AUTHORIZED","SUBMITTED","FILLED"}: _text(self.authorization_id,"authorization_id")
        if self.order_status in {"SUBMITTED","FILLED"}:
            for n in ("paper_candidate_id","canonical_risk_result_id","trading_symbol","action","option_type","position_side"): _text(getattr(self,n),n)
            if (self.action,self.option_type) not in {("BUY","CALL"),("SELL","PUT")} or self.position_side!="LONG": raise ValueError("Only long BUY/CALL or SELL/PUT premium is supported.")
            for n in ("quantity","lots"): _pos_int(getattr(self,n),n)
            _pos(self.reference_price,"reference_price")
        if self.order_status=="FILLED": _text(self.execution_result_id,"execution_result_id"); _pos(self.fill_price,"fill_price")
    def can_transition_to(self,next_status:str)->bool: return next_status in _NEXT.get(self.order_status,set())
    def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self): value=self.to_dict(); value.pop("paper_order_id"); value.pop("created_at"); value.pop("updated_at"); return value
