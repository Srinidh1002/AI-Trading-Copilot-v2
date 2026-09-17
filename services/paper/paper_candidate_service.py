"""Explicit, fail-closed paper candidate preparation and submission boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from services.contracts.final_decision_v1 import (
    Action,
    AuthorizationStatus,
    ExecutionStatus,
    FinalDecisionV1,
)
from services.contracts.paper_trade_candidate_v1 import PaperTradeCandidateV1
from services.contracts.canonical_risk_result_v1 import CanonicalRiskResultV1
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.trade_plan_v1 import TradePlanV1 as RiskPendingTradePlanV1
from services.observability import create_audit_event


class PaperCandidateStatus(str, Enum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEEDS_TRADE_PLAN = "NEEDS_TRADE_PLAN"
    MANUAL_APPROVAL_REQUIRED = "MANUAL_APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class PaperCandidatePreparation:
    decision: FinalDecisionV1
    candidate: PaperTradeCandidateV1 | None
    status: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    submitted: bool
    status: str
    reason: str
    executor_result: Mapping[str, Any] | None = None


def prepare_paper_candidate(
    decision: FinalDecisionV1,
    *,
    instrument_identity: Mapping[str, Any] | None = None,
    expires_at: datetime | str | None = None,
    session_validation: object | None = None,
    calendar: object | None = None,
    evaluated_at: datetime | str | None = None,
    session_policy: object | None = None,
    validation_mode: str = "STRICT_EXECUTION",
    canonical_trade_plan_result: CanonicalTradePlanResultV1 | None = None,
    trade_plan: RiskPendingTradePlanV1 | None = None,
    canonical_risk_result: CanonicalRiskResultV1 | None = None,
    audit_emitter=None,
    audit_context=None,
) -> PaperCandidatePreparation:
    """Validate supplied canonical data; never create a position or order."""
    if not isinstance(decision, FinalDecisionV1):
        raise TypeError("decision must be a FinalDecisionV1.")
    canonical_audit = canonical_risk_result is not None
    if canonical_audit and not isinstance(canonical_risk_result, CanonicalRiskResultV1):
        _emit_preparation(audit_emitter, audit_context, "PAPER_PREPARATION_STARTED", "STARTED", decision)
        value = _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk result is invalid.")
        _emit_preparation(audit_emitter, audit_context, "PAPER_PREPARATION_BLOCKED", "BLOCKED", decision, value)
        return value
    if canonical_audit:
        _emit_preparation(audit_emitter, audit_context, "PAPER_PREPARATION_STARTED", "STARTED", decision, canonical_risk_result)
    if session_validation is None and (calendar is not None or evaluated_at is not None or session_policy is not None):
        from services.market_session import validate_session_timestamp
        session_validation = validate_session_timestamp(symbol=decision.symbol, exchange=decision.exchange, market_timestamp=decision.market_timestamp, evaluated_at=evaluated_at or decision.created_at, calendar=calendar, policy=session_policy, validation_mode=validation_mode)
    session_reason = _session_rejection(session_validation, decision, "paper_preparation_allowed")
    if session_reason:
        value = _result(decision, PaperCandidateStatus.BLOCKED, session_reason)
        if canonical_audit: _emit_preparation(audit_emitter, audit_context, "PAPER_PREPARATION_BLOCKED", "BLOCKED", decision, value, canonical_risk_result)
        return value

    if canonical_risk_result is not None:
        value = _prepare_canonical_risk_candidate(decision, canonical_risk_result)
        event = "PAPER_PREPARATION_COMPLETED" if value.candidate is not None else "PAPER_PREPARATION_FAILED" if value.status == "FAILED" else "PAPER_PREPARATION_BLOCKED"
        _emit_preparation(audit_emitter, audit_context, event, "SUCCEEDED" if value.candidate is not None else "FAILED" if value.status == "FAILED" else "BLOCKED", decision, value, canonical_risk_result)
        return value

    plan_reason = _trade_plan_rejection(
        decision,
        canonical_trade_plan_result=canonical_trade_plan_result,
        trade_plan=trade_plan,
        evaluated_at=evaluated_at or decision.created_at,
    )
    if plan_reason:
        status = (
            PaperCandidateStatus.NEEDS_TRADE_PLAN
            if plan_reason == "P3-4 trade plan lacks P3-5 execution sizing."
            else PaperCandidateStatus.BLOCKED
        )
        return _result(decision, status, plan_reason)

    if decision.authorization_status == AuthorizationStatus.BLOCKED.value:
        return _result(decision, PaperCandidateStatus.BLOCKED, "Decision is blocked.")

    if decision.action not in {Action.BUY.value, Action.SELL.value}:
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            "A directional BUY or SELL decision is required.",
        )

    if decision.trade_plan is None:
        return _result(
            decision,
            PaperCandidateStatus.NEEDS_TRADE_PLAN,
            "A validated trade plan is required.",
        )

    if decision.authorization_status == AuthorizationStatus.ANALYSIS_ONLY.value:
        return _result(
            decision,
            PaperCandidateStatus.MANUAL_APPROVAL_REQUIRED,
            "ANALYSIS_ONLY cannot prepare an executable candidate.",
        )

    if decision.execution_status != ExecutionStatus.NOT_REQUESTED.value:
        return _result(
            decision,
            PaperCandidateStatus.BLOCKED,
            "Decision execution state must be NOT_REQUESTED.",
        )

    if not decision.data_health.validation_passed or decision.data_health.stale_sources:
        return _result(
            decision,
            PaperCandidateStatus.BLOCKED,
            "Fresh valid data health is required.",
        )

    if decision.risk.risk_status not in {"APPROVED", "VALID"}:
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            "Approved risk validation is required.",
        )

    identity = dict(instrument_identity or {})
    option_type = identity.get("option_type", decision.option_type)
    tradingsymbol = identity.get("tradingsymbol")
    token = identity.get("instrument_token")

    if option_type not in {"CE", "PE"} or not (tradingsymbol or token):
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            "Explicit option contract identity is required.",
        )

    plan = decision.trade_plan
    if plan.quantity is None or plan.quantity <= 0:
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            "Positive planned quantity is required.",
        )

    if expires_at is None:
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            "Explicit candidate expiry is required.",
        )

    entry = plan.entry_price
    if entry is None:
        if plan.entry_zone is None or len(plan.entry_zone) != 2:
            return _result(
                decision,
                PaperCandidateStatus.NOT_ELIGIBLE,
                "A validated entry price or entry zone is required.",
            )
        entry = plan.entry_zone[0]

    try:
        candidate = PaperTradeCandidateV1(
            snapshot_id=decision.snapshot_id,
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            exchange=decision.exchange,
            action=decision.action,
            option_type=option_type,
            tradingsymbol=tradingsymbol,
            instrument_token=token,
            entry=entry,
            stop_loss=plan.stop_loss,
            targets=plan.targets,
            quantity=plan.quantity,
            lots=plan.lots,
            lot_size=identity.get("lot_size"),
            risk_amount=plan.maximum_planned_loss,
            risk_reward=plan.risk_reward_ratio,
            created_at=decision.created_at,
            expires_at=expires_at,
            authorization_status=decision.authorization_status,
            execution_status=decision.execution_status,
            data_health_status=decision.data_health.overall_status,
            metadata={"decision_action": decision.action},
        )
    except Exception as exc:
        return _result(
            decision,
            PaperCandidateStatus.NOT_ELIGIBLE,
            f"Candidate validation failed: {type(exc).__name__}.",
        )

    return PaperCandidatePreparation(
        decision=decision,
        candidate=candidate,
        status=PaperCandidateStatus.MANUAL_APPROVAL_REQUIRED.value,
        warnings=("Candidate is prepared only; no paper order was submitted.",),
    )


def execute_paper_candidate(
    candidate: PaperTradeCandidateV1,
    decision: FinalDecisionV1,
    *,
    approved: bool,
    now: datetime | str,
    executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    session_validation: object | None = None,
    calendar: object | None = None,
    session_policy: object | None = None,
    trade_plan: RiskPendingTradePlanV1 | None = None,
    canonical_trade_plan_result: CanonicalTradePlanResultV1 | None = None,
) -> PaperExecutionResult:
    """Submit only a fresh, explicitly approved PAPER_READY paper candidate."""
    if not isinstance(candidate, PaperTradeCandidateV1) or not isinstance(
        decision,
        FinalDecisionV1,
    ):
        return _rejected("Canonical candidate and decision are required.")
    try:
        current = _to_datetime(now)
    except (TypeError, ValueError):
        return _rejected("Execution time must be a valid ISO-8601 timestamp.")

    if current.tzinfo is None:
        return _rejected("Execution time must be timezone-aware.")
    plan_reason = _trade_plan_rejection(
        decision,
        canonical_trade_plan_result=canonical_trade_plan_result,
        trade_plan=trade_plan,
        evaluated_at=current,
    )
    if plan_reason:
        return _rejected(plan_reason)
    if session_validation is None and (calendar is not None or session_policy is not None):
        from services.market_session import validate_session_timestamp
        session_validation = validate_session_timestamp(symbol=decision.symbol, exchange=decision.exchange, market_timestamp=decision.market_timestamp, evaluated_at=current, calendar=calendar, policy=session_policy, validation_mode="STRICT_EXECUTION")
    session_reason = _session_rejection(session_validation, decision, "paper_execution_allowed")
    if session_reason:
        return _rejected(session_reason)
    if not approved:
        return _rejected("Explicit manual approval is required.")
    if current >= candidate.expires_at:
        return _rejected("Paper candidate is stale or expired.")
    if (candidate.snapshot_id, candidate.decision_id) != (
        decision.snapshot_id,
        decision.decision_id,
    ):
        return _rejected("Candidate identity does not match the decision.")
    if candidate.symbol != decision.symbol or candidate.exchange != decision.exchange:
        return _rejected("Candidate market identity does not match the decision.")
    if candidate.action != decision.action:
        return _rejected("Candidate action does not match the decision.")
    if decision.authorization_status in {
        AuthorizationStatus.ANALYSIS_ONLY.value,
        AuthorizationStatus.BLOCKED.value,
    }:
        return _rejected("Decision authorization is not executable.")
    if decision.authorization_status != AuthorizationStatus.PAPER_READY.value:
        return _rejected("PAPER_READY authorization is required.")
    if candidate.authorization_status != AuthorizationStatus.PAPER_READY.value:
        return _rejected("Candidate PAPER_READY authorization is required.")
    if decision.execution_status != ExecutionStatus.NOT_REQUESTED.value:
        return _rejected("Decision execution state must be NOT_REQUESTED.")
    if candidate.execution_status != ExecutionStatus.NOT_REQUESTED.value:
        return _rejected("Candidate execution state must be NOT_REQUESTED.")
    if not decision.data_health.validation_passed or decision.data_health.stale_sources:
        return _rejected("Fresh valid data health is required.")
    if candidate.data_health_status not in {"VALID", "HEALTHY"}:
        return _rejected("Candidate data-health status is not executable.")
    if candidate.quantity <= 0:
        return _rejected("Positive candidate quantity is required.")
    if candidate.entry <= 0 or candidate.stop_loss <= 0:
        return _rejected("Positive entry and stop-loss values are required.")
    if len(candidate.targets) < 2:
        return _rejected("At least two validated targets are required.")

    payload: dict[str, Any] = {
        "decision": candidate.action,
        "master_decision": candidate.action,
        "approval_status": "APPROVED",
        "entry_allowed": True,
        "trade_action": "EXECUTE",
        "entry": candidate.entry,
        "stop_loss": candidate.stop_loss,
        "target1": candidate.targets[0],
        "target2": candidate.targets[1],
        "reason": "Explicitly approved canonical paper candidate.",
        "snapshot": {
            "timestamp": decision.market_timestamp.isoformat(),
            "ltp": candidate.entry,
        },
        "quantity": candidate.quantity,
    }

    if decision.confidence is not None:
        payload["confidence"] = decision.confidence
    if decision.risk.risk_level not in {"", "UNKNOWN"}:
        payload["risk_level"] = decision.risk.risk_level

    if executor is None:
        from services.trade.trade_engine import execute_paper_trade

        executor = execute_paper_trade

    try:
        result = executor(payload)
    except Exception:
        return _rejected("Paper executor failed.")

    if not isinstance(result, Mapping):
        return _rejected("Paper executor returned an invalid response.")

    return PaperExecutionResult(
        submitted=bool(result.get("executed")),
        status=str(result.get("status", "REJECTED")),
        reason=str(result.get("reason", "Paper executor returned no reason.")),
        executor_result=result,
    )


def _result(
    decision: FinalDecisionV1,
    status: PaperCandidateStatus,
    error: str,
) -> PaperCandidatePreparation:
    return PaperCandidatePreparation(
        decision=decision,
        candidate=None,
        status=status.value,
        errors=(error,),
    )


def _rejected(reason: str) -> PaperExecutionResult:
    return PaperExecutionResult(False, "REJECTED", reason)


def _prepare_canonical_risk_candidate(decision: FinalDecisionV1, result: CanonicalRiskResultV1) -> PaperCandidatePreparation:
    if not isinstance(result, CanonicalRiskResultV1):
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk result is invalid.")
    plan, sizing = result.trade_plan, result.sizing_result
    if result.risk_status != "RISK_APPROVED" or result.blockers or plan is None or sizing is None:
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk result is not approved for preparation.")
    if (result.snapshot_id, result.decision_id) != (decision.snapshot_id, decision.decision_id) or (plan.snapshot_id, plan.decision_id) != (decision.snapshot_id, decision.decision_id):
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk identity does not match decision.")
    if (plan.underlying_symbol, plan.exchange, plan.action, plan.option_type) != (decision.symbol, decision.exchange, decision.action, "CALL" if decision.action == "BUY" else "PUT" if decision.action == "SELL" else None):
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk direction does not match decision.")
    if plan.plan_status != "READY_FOR_RISK" or not plan.paper_preparation_eligible or plan.execution_eligible or plan.valid_until <= decision.created_at:
        return _result(decision, PaperCandidateStatus.BLOCKED, "Trade plan is not eligible for preparation.")
    if sizing.sizing_status != "APPROVED" or not sizing.risk_approved or not sizing.paper_preparation_eligible or sizing.execution_eligible or sizing.blockers:
        return _result(decision, PaperCandidateStatus.BLOCKED, "Sizing result is not approved for preparation.")
    if any(value is None for value in (plan.trading_symbol, plan.expiry_date, plan.strike, plan.lot_size, sizing.approved_lots, sizing.quantity, sizing.capital_required, sizing.maximum_loss, sizing.entry_price, sizing.stop_loss_price, sizing.target_price, sizing.reward_risk_ratio)):
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk result has incomplete sizing identity.")
    if sizing.quantity != sizing.approved_lots * plan.lot_size or any(value <= 0 for value in (plan.strike, plan.lot_size, sizing.approved_lots, sizing.quantity, sizing.capital_required, sizing.maximum_loss, sizing.entry_price, sizing.stop_loss_price, sizing.target_price, sizing.reward_risk_ratio)) or sizing.stop_loss_price >= sizing.entry_price or sizing.target_price <= sizing.entry_price:
        return _result(decision, PaperCandidateStatus.BLOCKED, "Canonical risk sizing values are invalid.")
    try:
        candidate = PaperTradeCandidateV1(snapshot_id=decision.snapshot_id, decision_id=decision.decision_id, symbol=decision.symbol, exchange=decision.exchange, action=decision.action, option_type="CE" if plan.option_type == "CALL" else "PE", position_side="LONG", tradingsymbol=plan.trading_symbol, instrument_token=None, entry=sizing.entry_price, stop_loss=sizing.stop_loss_price, targets=(sizing.target_price,), quantity=sizing.quantity, lots=sizing.approved_lots, lot_size=plan.lot_size, risk_amount=sizing.maximum_loss, risk_reward=sizing.reward_risk_ratio, created_at=decision.created_at, expires_at=plan.valid_until, authorization_status=decision.authorization_status, execution_status=decision.execution_status, data_health_status=decision.data_health.overall_status, metadata={"canonical_risk_result_id": result.result_id, "trade_plan_result_id": result.trade_plan_result_id, "trade_plan_id": plan.trade_plan_id, "sizing_result_id": sizing.sizing_result_id, "selection_id": plan.selection_id, "contract_id": plan.contract_id, "analysis_id": result.analysis_id, "capital_required": sizing.capital_required})
    except Exception as exc:
        return _result(decision, PaperCandidateStatus.NOT_ELIGIBLE, f"Candidate validation failed: {type(exc).__name__}.")
    return PaperCandidatePreparation(decision=decision, candidate=candidate, status=PaperCandidateStatus.MANUAL_APPROVAL_REQUIRED.value, warnings=("Sized candidate is prepared only; no paper order was submitted.",))


def _emit_preparation(emitter, context, event_type, outcome, decision, preparation=None, risk_result=None):
    """Emit bounded canonical-preparation diagnostics without affecting preparation."""
    if emitter is None:
        return
    plan = getattr(risk_result, "trade_plan", None); sizing = getattr(risk_result, "sizing_result", None); candidate = getattr(preparation, "candidate", None)
    attributes = {"canonical_risk_result_id": getattr(risk_result, "result_id", None), "trade_plan_result_id": getattr(risk_result, "trade_plan_result_id", None), "trade_plan_id": getattr(plan, "trade_plan_id", None), "sizing_result_id": getattr(sizing, "sizing_result_id", None), "option_type": getattr(plan, "option_type", None), "position_side": getattr(candidate, "position_side", None), "trading_symbol": getattr(plan, "trading_symbol", None), "expiry_date": getattr(plan, "expiry_date", None).isoformat() if getattr(plan, "expiry_date", None) else None, "strike": getattr(plan, "strike", None), "lot_size": getattr(plan, "lot_size", None), "approved_lots": getattr(sizing, "approved_lots", None), "quantity": getattr(sizing, "quantity", None), "capital_required": getattr(sizing, "capital_required", None), "maximum_loss": getattr(sizing, "maximum_loss", None), "risk_status": getattr(risk_result, "risk_status", None), "preparation_status": getattr(preparation, "status", None), "blocker_count": len(getattr(risk_result, "blockers", ())), "warning_count": len(getattr(preparation, "warnings", ())) }
    try:
        emitter.emit(create_audit_event(event_type, component="paper.candidate", operation="prepare_paper_candidate", outcome=outcome, context=context, snapshot_id=decision.snapshot_id, decision_id=decision.decision_id, symbol=decision.symbol, exchange=decision.exchange, action=decision.action, attributes={key: value for key, value in attributes.items() if value is not None}))
    except Exception:
        pass


def _trade_plan_rejection(
    decision: FinalDecisionV1,
    *,
    canonical_trade_plan_result: CanonicalTradePlanResultV1 | None,
    trade_plan: RiskPendingTradePlanV1 | None,
    evaluated_at: datetime | str,
) -> str | None:
    """Reject P3-4 inputs before legacy sizing or executor code is reached."""
    if canonical_trade_plan_result is None and trade_plan is None:
        return None
    if canonical_trade_plan_result is not None:
        if not isinstance(canonical_trade_plan_result, CanonicalTradePlanResultV1):
            return "Canonical trade-plan result is invalid."
        if canonical_trade_plan_result.result_status != "PLAN_CREATED":
            return "Canonical trade-plan result is not plan-created."
        if (canonical_trade_plan_result.snapshot_id, canonical_trade_plan_result.decision_id) != (decision.snapshot_id, decision.decision_id):
            return "Canonical trade-plan identity does not match decision."
        if trade_plan is not None and trade_plan != canonical_trade_plan_result.trade_plan:
            return "Explicit trade plan does not match canonical trade-plan result."
        trade_plan = canonical_trade_plan_result.trade_plan
    if not isinstance(trade_plan, RiskPendingTradePlanV1):
        return "Canonical trade plan is missing or invalid."
    if (trade_plan.snapshot_id, trade_plan.decision_id) != (decision.snapshot_id, decision.decision_id):
        return "Trade plan identity does not match decision."
    if trade_plan.underlying_symbol != decision.symbol or trade_plan.exchange != decision.exchange:
        return "Trade plan market identity does not match decision."
    if trade_plan.action != decision.action:
        return "Trade plan action does not match decision."
    if trade_plan.plan_status != "READY_FOR_RISK" or not trade_plan.paper_preparation_eligible:
        return "Trade plan is not ready for risk validation."
    moment = _to_datetime(evaluated_at)
    if moment.tzinfo is None:
        return "Trade-plan evaluation time must be timezone-aware."
    if trade_plan.valid_until <= moment:
        return "Trade plan is stale or expired."
    if not trade_plan.execution_eligible:
        return "P3-4 trade plan lacks P3-5 execution sizing."
    if any(value is None for value in (trade_plan.quantity, trade_plan.lots, trade_plan.capital_required)):
        return "P3-5 execution sizing is incomplete."
    return None


def _session_rejection(session_validation: object | None, decision: FinalDecisionV1, permission: str) -> str | None:
    if session_validation is None:
        return None
    if getattr(session_validation, "symbol", decision.symbol) != decision.symbol or getattr(session_validation, "exchange", decision.exchange) != decision.exchange:
        return "Market session identity does not match decision."
    trading_date = getattr(session_validation, "trading_date", decision.market_timestamp.date())
    if trading_date != decision.market_timestamp.date():
        return "Market session date does not match decision."
    if not getattr(session_validation, permission, False):
        return next(iter(getattr(session_validation, "blockers", ())), "Market session blocks paper operation.")
    return None


def _to_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError("value must be a datetime or ISO-8601 string.")
