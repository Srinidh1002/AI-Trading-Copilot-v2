"""Explicit canonical paper-execution orchestration; no analysis/risk/session reruns."""
from datetime import datetime,timezone
from uuid import uuid4
from services.contracts.canonical_risk_result_v1 import CanonicalRiskResultV1
from services.contracts.paper_execution_authorization_v1 import PaperExecutionAuthorizationV1
from services.contracts.paper_execution_request_v1 import PaperExecutionRequestV1
from services.contracts.canonical_paper_execution_result_v1 import CanonicalPaperExecutionResultV1
from services.paper.paper_candidate_service import prepare_paper_candidate
from services.paper.authorization import validate_paper_execution_authorization
from services.paper.executor import execute_paper_order
def run_canonical_paper_execution(*,canonical_risk_result,authorization,session_validation,available_capital=None,requested_lots=None,paper_candidate=None,execution_request=None,idempotency_store=None,clock=None,paper_candidate_id_factory=None,execution_request_id_factory=None,authorization_result_id_factory=None,execution_result_id_factory=None,canonical_result_id_factory=None):
 if not isinstance(canonical_risk_result,CanonicalRiskResultV1):raise TypeError("canonical_risk_result must be CanonicalRiskResultV1.")
 if authorization is not None and not isinstance(authorization,PaperExecutionAuthorizationV1):raise TypeError("authorization must be PaperExecutionAuthorizationV1 or None.")
 now=(clock or (lambda:datetime.now(timezone.utc)))()
 if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError("clock must return timezone-aware datetime.")
 rid=(canonical_result_id_factory or (lambda:str(uuid4())))()
 def out(status,reason,**kw):return CanonicalPaperExecutionResultV1(rid,now,status,snapshot_id=canonical_risk_result.snapshot_id,analysis_id=canonical_risk_result.analysis_id,decision_id=canonical_risk_result.decision_id,trade_plan_result_id=canonical_risk_result.trade_plan_result_id,trade_plan_id=getattr(canonical_risk_result.trade_plan,"trade_plan_id",None),sizing_result_id=canonical_risk_result.sizing_result_id,canonical_risk_result_id=canonical_risk_result.result_id,blockers=(reason,),**kw)
 if canonical_risk_result.risk_status=="NO_ACTION":return out("NO_ACTION","canonical_risk_no_action")
 if canonical_risk_result.risk_status!="RISK_APPROVED":return out("PREPARATION_BLOCKED","canonical_risk_not_approved")
 preparation=None
 if paper_candidate is None:
  preparation=prepare_paper_candidate(canonical_risk_result.decision,canonical_risk_result=canonical_risk_result)
  paper_candidate=preparation.candidate
 if paper_candidate is None:return out("PREPARATION_BLOCKED","paper_candidate_unavailable",preparation_status=getattr(preparation,"status",None))
 candidate_id=(paper_candidate_id_factory or (lambda:paper_candidate.snapshot_id+":"+paper_candidate.decision_id))()
 if execution_request is None:
  plan=canonical_risk_result.trade_plan;sizing=canonical_risk_result.sizing_result
  try:execution_request=PaperExecutionRequestV1((execution_request_id_factory or (lambda:str(uuid4())))(),now,authorization.authorization_id if authorization else "missing",authorization.idempotency_key if authorization else "missing",canonical_risk_result.snapshot_id,canonical_risk_result.analysis_id,canonical_risk_result.decision_id,canonical_risk_result.trade_plan_result_id,plan.trade_plan_id,sizing.sizing_result_id,canonical_risk_result.result_id,candidate_id,plan.underlying_symbol,plan.exchange,plan.action,plan.option_type,"LONG",plan.trading_symbol,plan.expiry_date,plan.strike,plan.lot_size,sizing.quantity,sizing.approved_lots,sizing.entry_price,sizing.stop_loss_price,sizing.target_price,sizing.capital_required,sizing.maximum_loss,sizing.reward_risk_ratio,plan.valid_from,plan.valid_until)
  except (TypeError,ValueError):return out("REQUEST_BLOCKED","execution_request_construction_failed",paper_candidate_id=candidate_id)
 auth_result=validate_paper_execution_authorization(execution_request=execution_request,authorization=authorization,session_validation=session_validation,clock=lambda:now,result_id_factory=authorization_result_id_factory)
 if auth_result.authorization_status!="AUTHORIZED":return out("AUTHORIZATION_BLOCKED","authorization_not_authorized",paper_candidate_id=candidate_id,execution_request_id=execution_request.execution_request_id,authorization_id=getattr(authorization,"authorization_id",None),authorization_result_id=auth_result.authorization_result_id,idempotency_key=execution_request.idempotency_key,authorization_status=auth_result.authorization_status)
 execution=execute_paper_order(execution_request=execution_request,authorization_result=auth_result,idempotency_store=idempotency_store,clock=lambda:now,execution_result_id_factory=execution_result_id_factory)
 base=dict(paper_candidate_id=candidate_id,execution_request_id=execution_request.execution_request_id,authorization_id=authorization.authorization_id,authorization_result_id=auth_result.authorization_result_id,execution_result_id=execution.execution_result_id,idempotency_key=execution_request.idempotency_key,underlying_symbol=execution_request.underlying_symbol,exchange=execution_request.exchange,action=execution_request.action,option_type=execution_request.option_type,position_side=execution_request.position_side,trading_symbol=execution_request.trading_symbol,quantity=execution_request.quantity,lots=execution_request.lots,authorization_status=auth_result.authorization_status,execution_status=execution.execution_status)
 if execution.execution_status=="FILLED":return CanonicalPaperExecutionResultV1(rid,now,"EXECUTED",reference_price=execution.reference_price,fill_price=execution.fill_price,capital_used=execution.capital_used,realized_maximum_loss=execution.realized_maximum_loss,submitted_at=execution.submitted_at,filled_at=execution.filled_at,**base)
 if execution.execution_status=="DUPLICATE":return out("DUPLICATE","execution_duplicate",**base)
 return out("EXECUTION_BLOCKED","execution_blocked",**base)
