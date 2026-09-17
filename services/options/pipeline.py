"""Optional, side-effect-free option selection and trade-plan orchestration."""

from __future__ import annotations

from uuid import uuid4

from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.observability.events import create_audit_event

from .selection import select_option_contract
from .trade_plan import build_trade_plan


def create_canonical_trade_plan(
    *, snapshot, analysis, decision, universe, session_validation=None,
    selection_policy=None, trade_plan_policy=None, requested_expiry=None,
    requested_strike=None, entry_reference_price=None, entry_price_source=None,
    stop_loss_price=None, stop_loss_source=None, target_price=None,
    target_source=None, contract_expiry_at=None, session_close_at=None,
    clock=None, selection_id_factory=None, trade_plan_id_factory=None,
    result_id_factory=None, audit_emitter=None, audit_context=None,
):
    """Create a canonical P3-4 result without changing default runtime routes.

    Audit emission is intentionally best-effort: it receives compact scalar
    context only and cannot affect the canonical result.
    """
    now = (clock() if clock else decision.created_at)
    result_id = (result_id_factory or (lambda: str(uuid4())))()
    analysis_id = analysis.analysis_id if analysis else None

    def result(status, selection=None, plan=None, blockers=()):
        return CanonicalTradePlanResultV1(
            result_id, now, snapshot.snapshot_id, analysis_id, decision.decision_id,
            decision, selection, plan, status, blockers=tuple(blockers),
        )

    def emit(event_type, outcome, *, selection=None, plan=None, blockers=()):
        _emit_audit(
            audit_emitter, audit_context, event_type, outcome, now=now,
            snapshot_id=snapshot.snapshot_id, analysis_id=analysis_id,
            decision=decision, selection=selection, plan=plan, blockers=blockers,
        )

    if getattr(session_validation, "analysis_allowed", True) is False:
        blockers = tuple(session_validation.blockers)
        emit("OPTION_SELECTION_BLOCKED", "BLOCKED", blockers=blockers)
        return result("BLOCKED", blockers=blockers)
    if decision.action not in {"BUY", "SELL"}:
        return result("NO_ACTION")
    if decision.authorization_status == "BLOCKED":
        blockers = ("Decision is blocked.",)
        emit("OPTION_SELECTION_BLOCKED", "BLOCKED", blockers=blockers)
        return result("BLOCKED", blockers=blockers)

    emit("OPTION_SELECTION_STARTED", "STARTED")
    try:
        selection = select_option_contract(
            decision, universe, now=now, policy=selection_policy,
            snapshot_id=snapshot.snapshot_id, requested_expiry=requested_expiry,
            requested_strike=requested_strike, id_factory=selection_id_factory,
        )
    except Exception:
        blockers = ("Option selection failed.",)
        emit("OPTION_SELECTION_FAILED", "FAILED", blockers=blockers)
        return result("FAILED", blockers=blockers)
    if not selection.selection_valid:
        emit("OPTION_SELECTION_BLOCKED", "BLOCKED", selection=selection, blockers=selection.blockers)
        return result("BLOCKED", selection=selection, blockers=selection.blockers)

    emit("OPTION_SELECTION_COMPLETED", "SUCCEEDED", selection=selection)
    emit("TRADE_PLAN_STARTED", "STARTED", selection=selection)
    try:
        plan = build_trade_plan(
            snapshot_id=snapshot.snapshot_id, analysis_id=analysis_id,
            decision_id=decision.decision_id, action=decision.action,
            selected_contract=selection, policy=trade_plan_policy,
            session_close_at=session_close_at, contract_expiry_at=contract_expiry_at,
            entry_reference_price=entry_reference_price,
            entry_price_source=entry_price_source, stop_loss_price=stop_loss_price,
            stop_loss_source=stop_loss_source, target_price=target_price,
            target_source=target_source, clock=lambda: now,
            id_factory=trade_plan_id_factory,
        )
    except Exception:
        blockers = ("Trade-plan construction failed.",)
        emit("TRADE_PLAN_FAILED", "FAILED", selection=selection, blockers=blockers)
        return result("FAILED", selection=selection, blockers=blockers)

    if plan.plan_status == "READY_FOR_RISK":
        emit("TRADE_PLAN_COMPLETED", "SUCCEEDED", selection=selection, plan=plan)
        return result("PLAN_CREATED", selection, plan)
    emit("TRADE_PLAN_BLOCKED", "BLOCKED", selection=selection, plan=plan, blockers=plan.blockers)
    status = "INSUFFICIENT_DATA" if plan.plan_status == "INSUFFICIENT_DATA" else "BLOCKED"
    return result(status, selection, plan, plan.blockers)


def _emit_audit(emitter, context, event_type, outcome, *, now, snapshot_id, analysis_id, decision, selection=None, plan=None, blockers=()):
    """Emit compact audit data; the observability boundary is always fail-open."""
    if emitter is None:
        return
    expiry_date = getattr(selection, "expiry_date", None) or getattr(plan, "expiry_date", None)
    attributes = {
        "option_type": getattr(selection, "option_type", None) or getattr(plan, "option_type", None),
        "expiry_date": expiry_date.isoformat() if expiry_date is not None else None,
        "strike": getattr(selection, "strike", None) or getattr(plan, "strike", None),
        "lot_size": getattr(selection, "lot_size", None) or getattr(plan, "lot_size", None),
        "expiry_policy": getattr(selection, "expiry_selection_policy", None),
        "strike_policy": getattr(selection, "strike_selection_policy", None),
        "reference_price_source": getattr(selection, "reference_price_source", None),
        "plan_status": getattr(plan, "plan_status", None),
        "blocker_count": len(tuple(blockers)),
        "warning_count": len(tuple(getattr(selection, "warnings", ())) + tuple(getattr(plan, "warnings", ()))),
    }
    try:
        event = create_audit_event(
            event_type, component="options.pipeline", operation="create_canonical_trade_plan",
            outcome=outcome, severity="WARNING" if outcome in {"BLOCKED", "FAILED"} else "INFO",
            context=context, clock=lambda: now, snapshot_id=snapshot_id,
            analysis_id=analysis_id, decision_id=decision.decision_id,
            symbol=decision.symbol, exchange=decision.exchange, action=decision.action,
            attributes=attributes,
        )
        emit = getattr(emitter, "emit", emitter)
        emit(event)
    except Exception:
        pass
