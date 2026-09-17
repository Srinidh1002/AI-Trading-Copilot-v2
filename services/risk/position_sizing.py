"""Pure, deterministic P3-5B option-premium position sizing."""

from __future__ import annotations

import math
from datetime import datetime
from uuid import uuid4

from services.contracts.position_size_result_v1 import PositionSizeResultV1
from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.contracts.trade_plan_v1 import TradePlanV1
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.observability import create_audit_event


def calculate_position_size(*, trade_plan, risk_policy, available_capital=None, requested_lots=None, clock=None, sizing_result_id_factory=None, audit_emitter=None, audit_context=None) -> PositionSizeResultV1:
    """Size a supplied P3-4 plan without selecting, rebuilding, or executing it."""
    if not isinstance(trade_plan, TradePlanV1):
        raise TypeError("trade_plan must be TradePlanV1.")
    if not isinstance(risk_policy, RiskPolicyV1):
        raise TypeError("risk_policy must be RiskPolicyV1.")
    now = (clock or (lambda: trade_plan.created_at))()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime.")
    result_id = (sizing_result_id_factory or (lambda: str(uuid4())))()
    capital = risk_policy.capital_base if available_capital is None else _positive(available_capital, "available_capital")
    if available_capital is None:
        capital = _positive(capital, "available_capital")
    if requested_lots is not None and (isinstance(requested_lots, bool) or not isinstance(requested_lots, int) or requested_lots <= 0):
        raise ValueError("requested_lots must be a positive integer.")
    _emit_sizing(audit_emitter, audit_context, "POSITION_SIZING_STARTED", "STARTED", trade_plan, requested_lots=requested_lots)

    def outcome(status, blocker, *, zero_size=False):
        value = _non_approved(trade_plan, result_id, now, status, blocker, requested_lots=requested_lots, zero_size=zero_size)
        _emit_sizing(audit_emitter, audit_context, "POSITION_SIZING_FAILED" if status == "FAILED" else "POSITION_SIZING_BLOCKED", "FAILED" if status == "FAILED" else "BLOCKED", trade_plan, value, requested_lots)
        return value

    if trade_plan.plan_status != "READY_FOR_RISK":
        return outcome("BLOCKED", "Trade plan is not READY_FOR_RISK.")
    if not trade_plan.paper_preparation_eligible:
        return outcome("BLOCKED", "Trade plan is not paper-preparation eligible.")
    if trade_plan.execution_eligible:
        return outcome("BLOCKED", "Trade plan unexpectedly permits execution.")
    if trade_plan.valid_until <= now:
        return outcome("BLOCKED", "Trade plan is expired.")
    if any(getattr(trade_plan, name) is None for name in ("selection_id", "trade_plan_id", "contract_id", "trading_symbol", "expiry_date", "strike", "lot_size", "option_type")):
        return outcome("BLOCKED", "Trade plan contract identity is incomplete.")
    if (trade_plan.underlying_symbol, trade_plan.exchange) not in SUPPORTED_MARKET_IDENTITIES:
        return outcome("BLOCKED", "Trade plan underlying/exchange is unsupported.")
    if (trade_plan.action, trade_plan.option_type) not in {("BUY", "CALL"), ("SELL", "PUT")}:
        return outcome("BLOCKED", "Trade plan action and option type are inconsistent.")

    entry, stop, target = trade_plan.entry_reference_price, trade_plan.stop_loss_price, trade_plan.target_price
    if not _is_positive(entry) or not _is_positive(stop) or not _is_positive(target):
        return outcome("INVALID_RISK", "Entry, stop-loss, and target prices must be positive.")
    if stop >= entry:
        return outcome("INVALID_RISK", "Stop-loss must be below entry for long premium.")
    if target <= entry:
        return outcome("INVALID_RISK", "Target must be above entry for long premium.")

    per_unit_risk = entry - stop
    per_lot_risk = per_unit_risk * trade_plan.lot_size
    per_lot_capital = entry * trade_plan.lot_size
    reward_per_unit = target - entry
    if not _is_positive(per_unit_risk) or not _is_positive(per_lot_risk):
        return outcome("INVALID_RISK", "Per-unit and per-lot risk must be positive.")
    effective_capital_limit = min(capital, risk_policy.maximum_capital_per_trade, capital * risk_policy.maximum_capital_fraction)
    effective_risk_limit = min(risk_policy.maximum_risk_per_trade, capital * risk_policy.maximum_risk_fraction)
    capital_lots = math.floor(effective_capital_limit / per_lot_capital)
    risk_lots = math.floor(effective_risk_limit / per_lot_risk)
    quantity_lots = math.floor(risk_policy.maximum_quantity / trade_plan.lot_size)
    policy_lots = risk_policy.maximum_lots

    if capital_lots < 1 or risk_lots < 1:
        return outcome("INSUFFICIENT_CAPITAL", "Capital or risk limit cannot fund one lot.", zero_size=risk_policy.insufficient_capital_behavior == "ZERO_SIZE")
    if quantity_lots < 1 or policy_lots < 1:
        return outcome("LIMIT_EXCEEDED", "Policy count limit cannot support one lot.")
    approved_lots = min(capital_lots, risk_lots, quantity_lots, policy_lots)
    demand = policy_lots if requested_lots is None else requested_lots
    approved_lots = min(approved_lots, demand)
    quantity = approved_lots * trade_plan.lot_size
    capital_required = entry * quantity
    maximum_loss = per_unit_risk * quantity
    reward_amount = reward_per_unit * quantity
    reward_risk_ratio = reward_amount / maximum_loss
    if reward_risk_ratio < risk_policy.minimum_reward_risk_ratio:
        return outcome("INVALID_RISK", "Reward-risk ratio is below the policy minimum.")
    if approved_lots < 1 or quantity < 1 or capital_required > effective_capital_limit or maximum_loss > effective_risk_limit:
        return outcome("LIMIT_EXCEEDED", "No policy-compliant positive size remains.")
    value = PositionSizeResultV1(
        sizing_result_id=result_id, created_at=now, snapshot_id=trade_plan.snapshot_id, analysis_id=trade_plan.analysis_id,
        decision_id=trade_plan.decision_id, selection_id=trade_plan.selection_id, trade_plan_id=trade_plan.trade_plan_id,
        contract_id=trade_plan.contract_id, underlying_symbol=trade_plan.underlying_symbol, exchange=trade_plan.exchange,
        action=trade_plan.action, option_type=trade_plan.option_type, trading_symbol=trade_plan.trading_symbol,
        expiry_date=trade_plan.expiry_date, strike=trade_plan.strike, lot_size=trade_plan.lot_size,
        entry_price=entry, stop_loss_price=stop, target_price=target, available_capital=capital,
        capital_limit=effective_capital_limit, risk_limit=effective_risk_limit, per_unit_risk=per_unit_risk,
        per_lot_risk=per_lot_risk, requested_lots=demand, approved_lots=approved_lots, quantity=quantity,
        capital_required=capital_required, maximum_loss=maximum_loss, reward_amount=reward_amount,
        reward_risk_ratio=reward_risk_ratio, sizing_status="APPROVED", risk_approved=True,
        paper_preparation_eligible=True, execution_eligible=False,
    )
    _emit_sizing(audit_emitter, audit_context, "POSITION_SIZING_COMPLETED", "SUCCEEDED", trade_plan, value, requested_lots)
    return value


def _emit_sizing(emitter, context, event_type, outcome, plan, result=None, requested_lots=None):
    """Best-effort bounded audit emission that cannot affect sizing."""
    if emitter is None:
        return
    attributes = {
        "trade_plan_id": plan.trade_plan_id, "sizing_result_id": getattr(result, "sizing_result_id", None),
        "option_type": plan.option_type, "position_side": "LONG", "trading_symbol": plan.trading_symbol,
        "expiry_date": plan.expiry_date.isoformat() if plan.expiry_date else None, "strike": plan.strike,
        "lot_size": plan.lot_size, "requested_lots": requested_lots,
        "approved_lots": getattr(result, "approved_lots", None), "quantity": getattr(result, "quantity", None),
        "capital_limit": getattr(result, "capital_limit", None), "risk_limit": getattr(result, "risk_limit", None),
        "capital_required": getattr(result, "capital_required", None), "maximum_loss": getattr(result, "maximum_loss", None),
        "sizing_status": getattr(result, "sizing_status", None), "blocker_count": len(getattr(result, "blockers", ())),
        "warning_count": len(getattr(result, "warnings", ())),
    }
    try:
        emitter.emit(create_audit_event(event_type, component="risk.position_sizing", operation="calculate_position_size", outcome=outcome, context=context, snapshot_id=plan.snapshot_id, analysis_id=plan.analysis_id, decision_id=plan.decision_id, symbol=plan.underlying_symbol, exchange=plan.exchange, action=plan.action, attributes={key: value for key, value in attributes.items() if value is not None}))
    except Exception:
        pass


def _non_approved(plan, result_id, now, status, blocker, *, requested_lots, zero_size=False) -> PositionSizeResultV1:
    """Preserve only source identity; never invent sizing outputs for failure paths."""
    return PositionSizeResultV1(
        sizing_result_id=result_id, created_at=now, snapshot_id=plan.snapshot_id, analysis_id=plan.analysis_id,
        decision_id=plan.decision_id, selection_id=plan.selection_id, trade_plan_id=plan.trade_plan_id,
        contract_id=plan.contract_id, underlying_symbol=plan.underlying_symbol, exchange=plan.exchange,
        action=plan.action, option_type=plan.option_type, trading_symbol=plan.trading_symbol,
        expiry_date=plan.expiry_date, strike=plan.strike, lot_size=plan.lot_size,
        entry_price=None, stop_loss_price=None, target_price=None, available_capital=None,
        capital_limit=None, risk_limit=None, per_unit_risk=None, per_lot_risk=None,
        requested_lots=requested_lots, approved_lots=0 if zero_size else None,
        quantity=0 if zero_size else None, capital_required=None, maximum_loss=None,
        reward_amount=None, reward_risk_ratio=None, sizing_status=status, risk_approved=False,
        paper_preparation_eligible=False, execution_eligible=False, blockers=(blocker,),
    )


def _positive(value, name):
    if not _is_positive(value):
        raise ValueError(f"{name} must be finite and positive.")
    return float(value)


def _is_positive(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0
