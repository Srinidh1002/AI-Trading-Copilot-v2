"""Immutable outcome of manual authorization validation."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
_STATUSES={"AUTHORIZED","NOT_APPROVED","EXPIRED","REVOKED","SESSION_INVALID","IDENTITY_MISMATCH","IDEMPOTENCY_MISMATCH","BLOCKED","FAILED"}
def _text(v,n):
 if not isinstance(v,str) or not v.strip(): raise ValueError(f"{n} is required.")
def _aware(v,n):
 if not isinstance(v,datetime) or v.tzinfo is None: raise ValueError(f"{n} must be timezone-aware.")
@dataclass(frozen=True,slots=True)
class PaperAuthorizationResultV1:
 authorization_result_id:str; created_at:datetime; authorization_status:str; execution_request_id:str; idempotency_key:str; validated_at:datetime; manual_authorization_valid:bool; paper_execution_eligible:bool
 authorization_id:str|None=None; paper_candidate_id:str|None=None; canonical_risk_result_id:str|None=None; sizing_result_id:str|None=None; trade_plan_id:str|None=None; session_id:str|None=None; underlying_symbol:str|None=None; exchange:str|None=None; action:str|None=None; option_type:str|None=None; position_side:str|None=None; trading_symbol:str|None=None; quantity:int|None=None; lots:int|None=None; authorization_valid_from:datetime|None=None; authorization_valid_until:datetime|None=None; blockers:tuple[str,...]=(); warnings:tuple[str,...]=(); schema_version:str="paper_authorization_result.v1"; execution_mode:str="PAPER"; live_execution_eligible:bool=False
 def __post_init__(self):
  if self.schema_version!="paper_authorization_result.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.authorization_status not in _STATUSES: raise ValueError("Invalid authorization result controls.")
  for n in ("authorization_result_id","execution_request_id","idempotency_key"): _text(getattr(self,n),n)
  _aware(self.created_at,"created_at");_aware(self.validated_at,"validated_at")
  for n in ("authorization_valid_from","authorization_valid_until"):
   if getattr(self,n) is not None:_aware(getattr(self,n),n)
  b,w=tuple(self.blockers),tuple(self.warnings)
  if any(not isinstance(x,str) or not x for x in b+w):raise ValueError("Invalid blockers or warnings.")
  object.__setattr__(self,"blockers",b);object.__setattr__(self,"warnings",w)
  if self.authorization_status=="AUTHORIZED":
   for n in ("authorization_id","paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","session_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol"): _text(getattr(self,n),n)
   if not self.manual_authorization_valid or not self.paper_execution_eligible or b or self.authorization_valid_from is None or self.authorization_valid_until is None or (self.underlying_symbol,self.exchange) not in SUPPORTED_MARKET_IDENTITIES or (self.action,self.option_type,self.position_side) not in {("BUY","CALL","LONG"),("SELL","PUT","LONG")}:raise ValueError("Invalid authorized result.")
  elif self.manual_authorization_valid or self.paper_execution_eligible or not b: raise ValueError("Non-authorized result must be blocked.")
  if self.authorization_status=="EXPIRED" and self.authorization_valid_until is None:raise ValueError("Expired result requires validity evidence.")
  if self.authorization_status=="REVOKED":_text(self.authorization_id,"authorization_id")
 def to_dict(self):return {n:(getattr(self,n).isoformat() if isinstance(getattr(self,n),datetime) else list(getattr(self,n)) if n in {"blockers","warnings"} else getattr(self,n)) for n in self.__dataclass_fields__}
 def to_json(self):return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
 def semantic_dict(self):d=self.to_dict();d.pop("authorization_result_id");d.pop("created_at");return d
