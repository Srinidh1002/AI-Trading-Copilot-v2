"""Immutable manual paper-execution approval artifact."""
from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import date, datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
_STATUSES={"APPROVED","REVOKED","EXPIRED","BLOCKED"}; _MARKETS=SUPPORTED_MARKET_IDENTITIES
def _text(v,n):
 if not isinstance(v,str) or not v.strip(): raise ValueError(f"{n} is required.")
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None: raise ValueError(f"{n} must be timezone-aware.")
def _pos(v,n):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0: raise ValueError(f"{n} must be finite and positive.")
def _int(v,n):
 if isinstance(v,bool) or not isinstance(v,int) or v<=0: raise ValueError(f"{n} must be a positive integer.")
@dataclass(frozen=True,slots=True)
class PaperExecutionAuthorizationV1:
 authorization_id:str; created_at:datetime; authorized_at:datetime; valid_from:datetime; valid_until:datetime; authorization_status:str; authorized_by:str; approval_reason:str; idempotency_key:str
 execution_request_id:str; paper_candidate_id:str; canonical_risk_result_id:str; sizing_result_id:str; trade_plan_id:str; decision_id:str; snapshot_id:str
 underlying_symbol:str; exchange:str; action:str; option_type:str; position_side:str; trading_symbol:str; expiry_date:date; strike:float; quantity:int; lots:int; lot_size:int; session_id:str; session_date:date; session_exchange:str
 blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); schema_version:str="paper_execution_authorization.v1"; authorization_mode:str="MANUAL"; execution_mode:str="PAPER"; live_execution_eligible:bool=False
 def __post_init__(self):
  if self.schema_version!="paper_execution_authorization.v1" or self.authorization_mode!="MANUAL" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.authorization_status not in _STATUSES: raise ValueError("Invalid authorization controls.")
  for n in ("authorization_id","authorized_by","approval_reason","idempotency_key","execution_request_id","paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","decision_id","snapshot_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol","session_id","session_exchange"): _text(getattr(self,n),n)
  for n in ("created_at","authorized_at","valid_from","valid_until"): _aware(getattr(self,n),n)
  if self.created_at>self.authorized_at or self.valid_from>self.authorized_at or self.valid_until<=self.valid_from: raise ValueError("Invalid authorization times.")
  if not isinstance(self.expiry_date,date) or isinstance(self.expiry_date,datetime) or not isinstance(self.session_date,date) or isinstance(self.session_date,datetime): raise ValueError("Date bindings are required.")
  if (self.underlying_symbol,self.exchange) not in _MARKETS or self.session_exchange!=self.exchange: raise ValueError("Invalid market/session identity.")
  if (self.action,self.option_type) not in {("BUY","CALL"),("SELL","PUT")} or self.position_side!="LONG": raise ValueError("Only long premium is supported.")
  for n in ("strike",): _pos(getattr(self,n),n)
  for n in ("quantity","lots","lot_size"): _int(getattr(self,n),n)
  if self.quantity!=self.lots*self.lot_size: raise ValueError("quantity must equal lots times lot_size.")
  b,w=tuple(self.blockers),tuple(self.warnings)
  if any(not isinstance(x,str) or not x for x in b+w): raise ValueError("Invalid blockers or warnings.")
  object.__setattr__(self,"blockers",b);object.__setattr__(self,"warnings",w)
  if self.authorization_status=="APPROVED" and b: raise ValueError("Approved authorization cannot have blockers.")
  if self.authorization_status!="APPROVED" and not b: raise ValueError("Non-approved authorization requires blockers.")
 def to_dict(self): return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),(datetime,date)) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self): d=self.to_dict();d.pop("authorization_id");d.pop("created_at");return d
