from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.contracts.trade_plan_v1 import TradePlanV1
from services.risk import calculate_position_size


NOW = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)


def policy(**changes):
    values = dict(policy_id="risk-1", policy_name="Conservative", capital_base=100000, maximum_capital_per_trade=10000, maximum_capital_fraction=.1, maximum_risk_per_trade=2000, maximum_risk_fraction=.02, minimum_reward_risk_ratio=1.5, maximum_lots=10, maximum_quantity=500, allow_fractional_lots=False, require_stop_loss=True, require_target=True, require_positive_entry=True, require_positive_stop_loss=True, require_positive_target=True, require_stop_below_entry_for_long=True, require_target_above_entry_for_long=True, insufficient_capital_behavior="BLOCK")
    values.update(changes); return RiskPolicyV1(**values)


def plan(**changes):
    values = dict(trade_plan_id="plan-1", created_at=NOW, snapshot_id="snapshot-1", analysis_id="analysis-1", decision_id="decision-1", selection_id="selection-1", contract_id="contract-1", underlying_symbol="NIFTY", exchange="NSE", action="BUY", option_type="CALL", trading_symbol="NIFTY26JUL25000CE", expiry_date=date(2026, 7, 30), strike=25000, lot_size=50, entry_reference_price=100, entry_price_source="LAST", stop_loss_price=90, target_price=120, stop_loss_source="EXPLICIT", target_source="EXPLICIT", valid_from=NOW, valid_until=NOW + timedelta(minutes=5), plan_status="READY_FOR_RISK", paper_preparation_eligible=True)
    values.update(changes); return TradePlanV1(**values)


def size(**changes):
    values = dict(trade_plan=plan(), risk_policy=policy(), clock=lambda: NOW, sizing_result_id_factory=lambda: "size-1")
    values.update(changes); return calculate_position_size(**values)


@pytest.mark.parametrize("symbol,exchange,action,option_type", [("NIFTY", "NSE", "BUY", "CALL"), ("NIFTY", "NSE", "SELL", "PUT"), ("SENSEX", "BSE", "BUY", "CALL"), ("SENSEX", "BSE", "SELL", "PUT")])
def test_supported_long_premium_directions_are_approved(symbol, exchange, action, option_type):
    result = size(trade_plan=plan(underlying_symbol=symbol, exchange=exchange, action=action, option_type=option_type))
    assert result.sizing_status == "APPROVED" and result.execution_eligible is False


def test_default_formulas_and_multiple_lot_approval():
    result = size()
    assert (result.approved_lots, result.quantity, result.capital_required, result.maximum_loss, result.reward_amount, result.reward_risk_ratio) == (2, 100, 10000.0, 1000.0, 2000.0, 2.0)


@pytest.mark.parametrize("available,expected", [(5000, 1), (10000, 2), (6000, 1)])
def test_capital_limit_controls_lots(available, expected):
    rules = policy(maximum_capital_fraction=1.0, maximum_risk_fraction=1.0)
    assert size(available_capital=available, risk_policy=rules).approved_lots == expected


@pytest.mark.parametrize("risk,expected", [(500, 1), (1000, 2)])
def test_risk_limit_controls_lots(risk, expected):
    assert size(risk_policy=policy(maximum_risk_per_trade=risk, maximum_risk_fraction=1)).approved_lots == expected


def test_maximum_lots_quantity_and_requested_lots_are_enforced():
    assert size(risk_policy=policy(maximum_lots=1)).approved_lots == 1
    assert size(risk_policy=policy(maximum_quantity=50)).approved_lots == 1
    assert size(requested_lots=1).approved_lots == 1


def test_default_capital_id_clock_and_semantics_are_deterministic():
    result = size()
    assert result.available_capital == policy().capital_base and result.sizing_result_id == "size-1" and result.created_at == NOW
    assert result.semantic_dict() == size().semantic_dict()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_invalid_available_capital_is_rejected(value):
    with pytest.raises(ValueError): size(available_capital=value)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_requested_lots_is_rejected(value):
    with pytest.raises(ValueError): size(requested_lots=value)


def test_input_types_are_checked():
    with pytest.raises(TypeError): calculate_position_size(trade_plan=object(), risk_policy=policy())
    with pytest.raises(TypeError): calculate_position_size(trade_plan=plan(), risk_policy=object())


def test_non_ready_and_expired_plans_are_blocked():
    non_ready = plan(plan_status="BLOCKED", paper_preparation_eligible=False, blockers=("blocked",))
    expired = plan(valid_from=NOW - timedelta(days=2), valid_until=NOW - timedelta(days=1))
    assert size(trade_plan=non_ready).sizing_status == "BLOCKED"
    assert size(trade_plan=expired).sizing_status == "BLOCKED"


@pytest.mark.parametrize("field", ["selection_id", "contract_id", "trading_symbol", "expiry_date", "strike", "lot_size"])
def test_incomplete_identity_is_blocked_without_fabrication(field):
    value = plan(); object.__setattr__(value, field, None)
    result = size(trade_plan=value)
    assert result.sizing_status == "BLOCKED" and getattr(result, field) is None


@pytest.mark.parametrize("field", ["entry_reference_price", "stop_loss_price", "target_price"])
def test_missing_prices_are_invalid_risk(field):
    value = plan(); object.__setattr__(value, field, None)
    assert size(trade_plan=value).sizing_status == "INVALID_RISK"


@pytest.mark.parametrize("stop,target", [(100, 120), (110, 120), (90, 100), (90, 95)])
def test_invalid_long_premium_price_relationships_are_invalid_risk(stop, target):
    value = plan(); object.__setattr__(value, "stop_loss_price", stop); object.__setattr__(value, "target_price", target)
    assert size(trade_plan=value).sizing_status == "INVALID_RISK"


def test_reward_risk_below_policy_minimum_is_invalid_risk():
    assert size(risk_policy=policy(minimum_reward_risk_ratio=3)).sizing_status == "INVALID_RISK"


def test_effective_limit_and_risk_fields_are_reported():
    result = size()
    assert (result.capital_limit, result.risk_limit, result.per_unit_risk, result.per_lot_risk) == (10000.0, 2000.0, 10.0, 500.0)


@pytest.mark.parametrize("risk_policy,available,status", [(policy(maximum_capital_per_trade=100, maximum_capital_fraction=1), 100000, "INSUFFICIENT_CAPITAL"), (policy(maximum_risk_per_trade=100, maximum_risk_fraction=1), 100000, "INSUFFICIENT_CAPITAL"), (policy(maximum_quantity=25), 100000, "LIMIT_EXCEEDED")])
def test_zero_lot_constraints_map_to_safe_statuses(risk_policy, available, status):
    assert size(risk_policy=risk_policy, available_capital=available).sizing_status == status


def test_zero_size_policy_preserves_no_capital_or_loss():
    result = size(risk_policy=policy(insufficient_capital_behavior="ZERO_SIZE", maximum_capital_per_trade=100, maximum_capital_fraction=1))
    assert (result.approved_lots, result.quantity, result.capital_required, result.maximum_loss) == (0, 0, None, None)


def test_block_insufficient_capital_is_deterministic_and_noneligible():
    first = size(risk_policy=policy(maximum_capital_per_trade=100, maximum_capital_fraction=1))
    second = size(risk_policy=policy(maximum_capital_per_trade=100, maximum_capital_fraction=1))
    assert first.semantic_dict() == second.semantic_dict() and first.paper_preparation_eligible is False


def test_requested_lots_are_clamped_not_rejected():
    assert size(requested_lots=99).approved_lots == 2


@pytest.mark.parametrize("requested,approved", [(1, 1), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2)])
def test_requested_lot_boundary_is_deterministically_clamped(requested, approved):
    assert size(requested_lots=requested).approved_lots == approved


def test_exact_one_lot_approval_uses_lot_size_quantity():
    rules = policy(maximum_capital_fraction=1.0, maximum_risk_fraction=1.0)
    result = size(available_capital=5000, risk_policy=rules)
    assert (result.approved_lots, result.quantity) == (1, 50)


def test_capital_required_formula_is_entry_times_quantity():
    result = size()
    assert result.capital_required == result.entry_price * result.quantity


def test_maximum_loss_formula_is_per_unit_risk_times_quantity():
    result = size()
    assert result.maximum_loss == result.per_unit_risk * result.quantity


def test_reward_formula_is_target_minus_entry_times_quantity():
    result = size()
    assert result.reward_amount == (result.target_price - result.entry_price) * result.quantity


def test_reward_risk_formula_is_reward_over_maximum_loss():
    result = size()
    assert result.reward_risk_ratio == result.reward_amount / result.maximum_loss


@pytest.mark.parametrize("field", ["paper_preparation_eligible", "execution_eligible"])
def test_unexpected_trade_plan_eligibility_is_blocked(field):
    value = plan(); object.__setattr__(value, field, False if field == "paper_preparation_eligible" else True)
    result = size(trade_plan=value)
    assert result.sizing_status == "BLOCKED" and result.execution_eligible is False

def test_wait_plan_is_blocked_honestly():
    value = plan(plan_status="BLOCKED", paper_preparation_eligible=False, blockers=("wait",), action="WAIT", option_type=None, selection_id=None, contract_id=None, trading_symbol=None, expiry_date=None, strike=None, lot_size=None)
    result = size(trade_plan=value)
    assert (result.sizing_status, result.action, result.option_type) == ("BLOCKED", "WAIT", None)


def test_inputs_are_not_mutated():
    trade, rules = plan(), policy(); before_trade, before_rules = trade.to_dict(), rules.to_dict()
    size(trade_plan=trade, risk_policy=rules)
    assert trade.to_dict() == before_trade and rules.to_dict() == before_rules


def test_generated_ids_and_timestamps_do_not_change_semantics():
    later = NOW + timedelta(minutes=1)
    first = size(sizing_result_id_factory=lambda: "one", clock=lambda: NOW)
    second = size(sizing_result_id_factory=lambda: "two", clock=lambda: later)
    assert first.semantic_dict() == second.semantic_dict()


def test_sizing_imports_no_execution_dependencies(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("filesystem access")))
    before = set(sys.modules); assert size().sizing_status == "APPROVED"
    imported = set(sys.modules) - before
    assert not {name for name in imported if any(token in name.lower() for token in ("broker", "provider", "database", "trade_engine"))}
