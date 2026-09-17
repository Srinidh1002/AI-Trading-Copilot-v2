"""Fail-closed canonical risk validation; no execution integration."""
from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from services.contracts.canonical_risk_result_v1 import CanonicalRiskResultV1
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.observability import create_audit_event
from .position_sizing import calculate_position_size

def validate_canonical_risk(*,canonical_trade_plan_result,risk_policy,available_capital=None,requested_lots=None,session_validation=None,clock=None,sizing_result_id_factory=None,result_id_factory=None,audit_emitter=None,audit_context=None):
    if not isinstance(canonical_trade_plan_result,CanonicalTradePlanResultV1): raise TypeError("canonical_trade_plan_result must be CanonicalTradePlanResultV1.")
    if not isinstance(risk_policy,RiskPolicyV1): raise TypeError("risk_policy must be RiskPolicyV1.")
    if session_validation is not None and not isinstance(session_validation,MarketSessionValidationV1): raise TypeError("session_validation must be MarketSessionValidationV1.")
    source=canonical_trade_plan_result; now=(clock or (lambda:source.created_at))(); rid=(result_id_factory or (lambda:str(uuid4())))()
    plan=source.trade_plan; decision=source.decision
    _emit_risk(audit_emitter,audit_context,"RISK_VALIDATION_STARTED","STARTED",source,requested_lots=requested_lots)
    def result(status,blockers=(),sizing=None):
        value=CanonicalRiskResultV1(rid,now,source.snapshot_id,source.analysis_id,source.decision_id,source.result_id,sizing.sizing_result_id if sizing else None,decision,plan,sizing,status,blockers=tuple(blockers),warnings=tuple(getattr(sizing,"warnings",())))
        event="RISK_VALIDATION_COMPLETED" if status=="RISK_APPROVED" else "RISK_VALIDATION_FAILED" if status=="FAILED" else "RISK_VALIDATION_BLOCKED"
        _emit_risk(audit_emitter,audit_context,event,"SUCCEEDED" if status=="RISK_APPROVED" else "FAILED" if status=="FAILED" else "BLOCKED",source,value,requested_lots)
        return value
    if source.result_status=="NO_ACTION": return result("NO_ACTION")
    if source.result_status!="PLAN_CREATED": return result("BLOCKED",("Canonical trade-plan result is not plan-created.",))
    if plan is None: return result("BLOCKED",("Canonical result has no trade plan.",))
    if plan.plan_status!="READY_FOR_RISK" or not plan.paper_preparation_eligible or plan.execution_eligible: return result("BLOCKED",("Trade plan is not eligible for risk sizing.",))
    if plan.valid_until<=now: return result("BLOCKED",("Trade plan is expired.",))
    if (plan.snapshot_id,plan.decision_id,plan.underlying_symbol,plan.exchange)!=(source.snapshot_id,source.decision_id,decision.symbol,decision.exchange): return result("BLOCKED",("Trade-plan identity does not match canonical decision.",))
    if session_validation is not None:
        session_blocker=_session_blocker(session_validation,plan,decision)
        if session_blocker: return result("BLOCKED",(session_blocker,))
    sizing=calculate_position_size(trade_plan=plan,risk_policy=risk_policy,available_capital=available_capital,requested_lots=requested_lots,clock=lambda:now,sizing_result_id_factory=sizing_result_id_factory)
    status={"APPROVED":"RISK_APPROVED","INSUFFICIENT_CAPITAL":"INSUFFICIENT_CAPITAL","INVALID_RISK":"INVALID_RISK","LIMIT_EXCEEDED":"LIMIT_EXCEEDED","BLOCKED":"BLOCKED","FAILED":"FAILED"}.get(sizing.sizing_status,"FAILED")
    return result(status,() if status=="RISK_APPROVED" else sizing.blockers,sizing)

def _session_blocker(session,plan,decision):
    if (session.symbol,session.exchange)!=(decision.symbol,decision.exchange): return "Session identity does not match decision."
    if session.trading_date!=plan.created_at.date(): return "Session date does not match trade plan."
    if not session.analysis_allowed or session.stale or session.future_timestamp or not session.regular_session_open: return next(iter(session.blockers),"Market session blocks risk sizing.")
    return None

def _emit_risk(emitter,context,event_type,outcome,source,result=None,requested_lots=None):
    if emitter is None: return
    plan=source.trade_plan; sizing=getattr(result,"sizing_result",None)
    attributes={"trade_plan_result_id":source.result_id,"trade_plan_id":getattr(plan,"trade_plan_id",None),"canonical_risk_result_id":getattr(result,"result_id",None),"sizing_result_id":getattr(sizing,"sizing_result_id",None),"option_type":getattr(plan,"option_type",None),"position_side":"LONG" if getattr(plan,"action",None) in {"BUY","SELL"} else None,"trading_symbol":getattr(plan,"trading_symbol",None),"expiry_date":getattr(plan,"expiry_date",None).isoformat() if getattr(plan,"expiry_date",None) else None,"strike":getattr(plan,"strike",None),"lot_size":getattr(plan,"lot_size",None),"requested_lots":requested_lots,"approved_lots":getattr(sizing,"approved_lots",None),"quantity":getattr(sizing,"quantity",None),"capital_limit":getattr(sizing,"capital_limit",None),"risk_limit":getattr(sizing,"risk_limit",None),"capital_required":getattr(sizing,"capital_required",None),"maximum_loss":getattr(sizing,"maximum_loss",None),"sizing_status":getattr(sizing,"sizing_status",None),"risk_status":getattr(result,"risk_status",None),"blocker_count":len(getattr(result,"blockers",())),"warning_count":len(getattr(result,"warnings",()))}
    try: emitter.emit(create_audit_event(event_type,component="risk.pipeline",operation="validate_canonical_risk",outcome=outcome,context=context,snapshot_id=source.snapshot_id,analysis_id=source.analysis_id,decision_id=source.decision_id,symbol=source.decision.symbol,exchange=source.decision.exchange,action=source.decision.action,attributes={key:value for key,value in attributes.items() if value is not None}))
    except Exception: pass
