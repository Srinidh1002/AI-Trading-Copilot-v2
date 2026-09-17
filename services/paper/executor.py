"""Deterministic isolated paper-only full-fill executor."""
from datetime import datetime, timezone
from uuid import uuid4
from services.contracts.paper_execution_request_v1 import PaperExecutionRequestV1
from services.contracts.paper_authorization_result_v1 import PaperAuthorizationResultV1
from services.contracts.paper_execution_result_v1 import PaperExecutionResultV1

def execute_paper_order(*,execution_request,authorization_result,idempotency_store=None,clock=None,execution_result_id_factory=None):
 if not isinstance(execution_request,PaperExecutionRequestV1):raise TypeError("execution_request must be PaperExecutionRequestV1.")
 if not isinstance(authorization_result,PaperAuthorizationResultV1):raise TypeError("authorization_result must be PaperAuthorizationResultV1.")
 now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError("clock must return a timezone-aware datetime.")
 rid=(execution_result_id_factory or (lambda:str(uuid4())))()
 def blocked(reason,status="BLOCKED"):
  return PaperExecutionResultV1(rid,execution_request.execution_request_id,now,execution_request.idempotency_key,status,authorization_id=authorization_result.authorization_id,paper_candidate_id=authorization_result.paper_candidate_id,canonical_risk_result_id=authorization_result.canonical_risk_result_id,trade_plan_id=authorization_result.trade_plan_id,sizing_result_id=authorization_result.sizing_result_id,blockers=(reason,))
 if authorization_result.authorization_status!="AUTHORIZED" or not authorization_result.manual_authorization_valid or not authorization_result.paper_execution_eligible or authorization_result.live_execution_eligible or authorization_result.blockers:return blocked("authorization_not_usable")
 if now<execution_request.valid_from or now>=execution_request.valid_until:return blocked("execution_request_not_valid")
 if authorization_result.authorization_id!=execution_request.authorization_id:return blocked("authorization_identity_mismatch")
 for name in ("execution_request_id","idempotency_key","paper_candidate_id","canonical_risk_result_id","sizing_result_id","trade_plan_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol","quantity","lots"):
  if getattr(authorization_result,name)!=getattr(execution_request,name):return blocked("authorization_identity_mismatch")
 if idempotency_store is not None and idempotency_store.get(execution_request.idempotency_key) is not None:return blocked("idempotency_key_already_claimed","DUPLICATE")
 fill=execution_request.entry_reference_price; quantity=execution_request.quantity
 result=PaperExecutionResultV1(rid,execution_request.execution_request_id,now,execution_request.idempotency_key,"FILLED",authorization_id=authorization_result.authorization_id,paper_candidate_id=execution_request.paper_candidate_id,canonical_risk_result_id=execution_request.canonical_risk_result_id,trade_plan_id=execution_request.trade_plan_id,sizing_result_id=execution_request.sizing_result_id,underlying_symbol=execution_request.underlying_symbol,exchange=execution_request.exchange,action=execution_request.action,option_type=execution_request.option_type,position_side=execution_request.position_side,trading_symbol=execution_request.trading_symbol,requested_quantity=quantity,filled_quantity=quantity,requested_lots=execution_request.lots,filled_lots=execution_request.lots,reference_price=fill,fill_price=fill,capital_used=fill*quantity,realized_maximum_loss=(fill-execution_request.stop_loss_price)*quantity,submitted_at=now,filled_at=now)
 if idempotency_store is not None and not idempotency_store.claim(execution_request.idempotency_key,rid):return blocked("idempotency_key_already_claimed","DUPLICATE")
 return result
