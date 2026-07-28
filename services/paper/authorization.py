"""Pure manual paper-authorization validation; never submits an order."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from services.contracts.paper_execution_request_v1 import PaperExecutionRequestV1
from services.contracts.paper_execution_authorization_v1 import PaperExecutionAuthorizationV1
from services.contracts.paper_authorization_result_v1 import PaperAuthorizationResultV1

def validate_paper_execution_authorization(*,execution_request,authorization,session_validation=None,clock=None,result_id_factory=None):
 if not isinstance(execution_request,PaperExecutionRequestV1):raise TypeError("execution_request must be PaperExecutionRequestV1.")
 if authorization is not None and not isinstance(authorization,PaperExecutionAuthorizationV1):raise TypeError("authorization must be PaperExecutionAuthorizationV1 or None.")
 now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError("clock must return a timezone-aware datetime.")
 rid=(result_id_factory or (lambda:str(uuid4())))()
 def out(status,reason,auth=None):
  fields=dict(authorization_id=getattr(auth,"authorization_id",None),paper_candidate_id=getattr(auth,"paper_candidate_id",None),canonical_risk_result_id=getattr(auth,"canonical_risk_result_id",None),sizing_result_id=getattr(auth,"sizing_result_id",None),trade_plan_id=getattr(auth,"trade_plan_id",None),session_id=getattr(auth,"session_id",None),underlying_symbol=getattr(auth,"underlying_symbol",None),exchange=getattr(auth,"exchange",None),action=getattr(auth,"action",None),option_type=getattr(auth,"option_type",None),position_side=getattr(auth,"position_side",None),trading_symbol=getattr(auth,"trading_symbol",None),quantity=getattr(auth,"quantity",None),lots=getattr(auth,"lots",None),authorization_valid_from=getattr(auth,"valid_from",None),authorization_valid_until=getattr(auth,"valid_until",None))
  if status=="AUTHORIZED":fields.update(manual_authorization_valid=True,paper_execution_eligible=True,blockers=())
  else:fields.update(manual_authorization_valid=False,paper_execution_eligible=False,blockers=(reason,))
  return PaperAuthorizationResultV1(rid,now,status,execution_request.execution_request_id,execution_request.idempotency_key,now,**fields)
 if authorization is None:return out("NOT_APPROVED","Manual authorization is required.")
 if authorization.authorization_status=="REVOKED":return out("REVOKED","Authorization is revoked.",authorization)
 if authorization.authorization_status=="EXPIRED":return out("EXPIRED","Authorization is declared expired.",authorization)
 if authorization.authorization_status=="BLOCKED":return out("BLOCKED","Authorization is blocked.",authorization)
 if now<authorization.valid_from:return out("NOT_APPROVED","Authorization is not yet valid.",authorization)
 if now>=authorization.valid_until:return out("EXPIRED","Authorization has expired.",authorization)
 if authorization.execution_request_id!=execution_request.execution_request_id:return out("IDENTITY_MISMATCH","Execution request identity does not match.",authorization)
 if authorization.idempotency_key!=execution_request.idempotency_key:return out("IDEMPOTENCY_MISMATCH","Idempotency key does not match.",authorization)
 for name in ("paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","decision_id","snapshot_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol","expiry_date","strike","quantity","lots","lot_size"):
  if getattr(authorization,name)!=getattr(execution_request,name):return out("IDENTITY_MISMATCH",f"Authorization {name} does not match.",authorization)
 if session_validation is None:return out("SESSION_INVALID","Session validation is required.",authorization)
 if not getattr(session_validation,"paper_execution_allowed",False) or getattr(session_validation,"blockers",()):return out("SESSION_INVALID","Session validation blocks paper execution.",authorization)
 if getattr(session_validation,"validation_id",None)!=authorization.session_id or getattr(session_validation,"trading_date",None)!=authorization.session_date or getattr(session_validation,"exchange",None)!=authorization.session_exchange or getattr(session_validation,"symbol",None)!=authorization.underlying_symbol:return out("SESSION_INVALID","Session identity does not match authorization.",authorization)
 if getattr(session_validation,"stale",False) or getattr(session_validation,"future_timestamp",False):return out("SESSION_INVALID","Session validation is stale or future-dated.",authorization)
 return out("AUTHORIZED","",authorization)
