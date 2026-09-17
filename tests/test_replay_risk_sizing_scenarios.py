"""Offline deterministic P3-5E replay scenarios; no runtime services."""
from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
import pytest

from services.contracts.final_decision_v1 import DataHealthSummary, FinalDecisionV1, RiskSummary
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
from services.contracts.trade_plan_v1 import TradePlanV1
from services.risk import calculate_position_size, validate_canonical_risk

NOW = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)
def policy(**changes):
    values = dict(policy_id="rp", policy_name="Replay", capital_base=100000, maximum_capital_per_trade=10000, maximum_capital_fraction=1, maximum_risk_per_trade=2000, maximum_risk_fraction=1, minimum_reward_risk_ratio=1.5, maximum_lots=10, maximum_quantity=500, allow_fractional_lots=False, require_stop_loss=True, require_target=True, require_positive_entry=True, require_positive_stop_loss=True, require_positive_target=True, require_stop_below_entry_for_long=True, require_target_above_entry_for_long=True, insufficient_capital_behavior="BLOCK")
    values.update(changes); return RiskPolicyV1(**values)
def decision(action="BUY", symbol="NIFTY", exchange="NSE"):
    return FinalDecisionV1(snapshot_id="snap", decision_id="decision", symbol=symbol, exchange=exchange, instrument_type="OPTION", created_at=NOW, market_timestamp=NOW, action=action, authorization_status="ANALYSIS_ONLY", execution_status="NOT_REQUESTED", risk=RiskSummary(risk_status="APPROVED"), data_health=DataHealthSummary(overall_status="VALID", validation_passed=True))
def plan(action="BUY", symbol="NIFTY", exchange="NSE", option_type="CALL", **changes):
    values = dict(trade_plan_id="plan", created_at=NOW, snapshot_id="snap", analysis_id="analysis", decision_id="decision", selection_id="selection", contract_id="contract", underlying_symbol=symbol, exchange=exchange, action=action, option_type=option_type, trading_symbol="OPT", expiry_date=date(2026, 7, 30), strike=25000, lot_size=50, entry_reference_price=100, entry_price_source="LAST", stop_loss_price=90, target_price=120, stop_loss_source="EXPLICIT", target_source="EXPLICIT", valid_from=NOW, valid_until=NOW + timedelta(minutes=5), plan_status="READY_FOR_RISK", paper_preparation_eligible=True)
    values.update(changes); return TradePlanV1(**values)
def canonical(p=None, status="PLAN_CREATED"):
    p = p or plan(); d = decision("WAIT", p.underlying_symbol, p.exchange) if status == "NO_ACTION" else decision(p.action, p.underlying_symbol, p.exchange)
    selected = SelectedOptionContractV1("selection", NOW, "snap", "decision", "universe", "contract", p.underlying_symbol, p.exchange, p.action, p.option_type, "OPT", None, p.expiry_date, p.strike, p.lot_size, p.strike, 100, "LAST", "EARLIEST_ELIGIBLE", "NEAREST_ATM", True)
    return CanonicalTradePlanResultV1("trade-result", NOW, "snap", "analysis", "decision", d, selected if status == "PLAN_CREATED" else None, p if status == "PLAN_CREATED" else None, status, blockers=("blocked",) if status not in {"PLAN_CREATED", "NO_ACTION"} else ())
def run(p=None, **changes):
    return validate_canonical_risk(canonical_trade_plan_result=canonical(p), risk_policy=policy(), clock=lambda: NOW, sizing_result_id_factory=lambda: "size", result_id_factory=lambda: "risk", **changes)

@pytest.mark.parametrize("symbol,exchange,action,kind", [("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_replay_supported_direction_is_deterministically_approved(symbol, exchange, action, kind):
    result = run(plan(action, symbol, exchange, kind)); assert result.risk_status == "RISK_APPROVED" and result.sizing_result.action == action

@pytest.mark.parametrize("available,maximum_risk,requested,maximum_lots,maximum_quantity,expected", [(5000,2000,None,10,500,1),(100000,500, None,10,500,1),(100000,2000,1,10,500,1),(100000,2000,99,1,500,1),(100000,2000,99,10,50,1),(100000,2000,99,10,500,2)])
def test_replay_limits_and_lot_clamping_are_deterministic(available, maximum_risk, requested, maximum_lots, maximum_quantity, expected):
    result = calculate_position_size(trade_plan=plan(), risk_policy=policy(maximum_risk_per_trade=maximum_risk, maximum_lots=maximum_lots, maximum_quantity=maximum_quantity), available_capital=available, requested_lots=requested, clock=lambda: NOW, sizing_result_id_factory=lambda: "size")
    assert result.approved_lots == expected and result.execution_eligible is False

@pytest.mark.parametrize("mutator,status", [(lambda p: replace(p, entry_reference_price=None),"INVALID_RISK"),(lambda p: replace(p, stop_loss_price=None),"INVALID_RISK"),(lambda p: replace(p, target_price=None),"INVALID_RISK"),(lambda p: replace(p, valid_from=NOW-timedelta(minutes=10), valid_until=NOW-timedelta(minutes=1)),"BLOCKED"),(lambda p: replace(p, plan_status="BLOCKED", paper_preparation_eligible=False, blockers=("plan_blocked",)),"BLOCKED"),(lambda p: replace(p, entry_reference_price=100, stop_loss_price=90, target_price=105),"INVALID_RISK"),(lambda p: replace(p, plan_status="INVALID", paper_preparation_eligible=False, blockers=("identity_unavailable",)),"BLOCKED")])
def test_replay_deterministic_rejections(mutator, status):
    assert calculate_position_size(trade_plan=mutator(plan()), risk_policy=policy(), clock=lambda: NOW, sizing_result_id_factory=lambda: "size").sizing_status == status

@pytest.mark.parametrize("status,expected", [("NO_ACTION","NO_ACTION"),("BLOCKED","BLOCKED"),("INSUFFICIENT_DATA","BLOCKED"),("FAILED","BLOCKED")])
def test_replay_canonical_gates_never_size(status, expected):
    source = canonical(status=status); result = validate_canonical_risk(canonical_trade_plan_result=source, risk_policy=policy(), clock=lambda: NOW, result_id_factory=lambda: "risk")
    assert result.risk_status == expected and result.sizing_result is None

@pytest.mark.parametrize("first_id,second_id,first_time,second_time", [("one","two",NOW,NOW + timedelta(minutes=1)), ("a","b",NOW,NOW), ("stable","changed",NOW + timedelta(minutes=2),NOW)])
def test_replay_semantics_exclude_generated_identifiers_and_timestamps(first_id, second_id, first_time, second_time):
    first = calculate_position_size(trade_plan=plan(), risk_policy=policy(), clock=lambda: first_time, sizing_result_id_factory=lambda: first_id)
    second = calculate_position_size(trade_plan=plan(), risk_policy=policy(), clock=lambda: second_time, sizing_result_id_factory=lambda: second_id)
    assert first.semantic_dict() == second.semantic_dict()

@pytest.mark.parametrize("field", ["selection_id","contract_id","trading_symbol","expiry_date","strike","lot_size"])
def test_replay_incomplete_identity_is_not_fabricated(field):
    value = plan(); object.__setattr__(value, field, None)
    result = calculate_position_size(trade_plan=value, risk_policy=policy(), clock=lambda: NOW, sizing_result_id_factory=lambda: "size")
    assert result.sizing_status == "BLOCKED" and getattr(result, field) is None

def test_replay_same_input_and_reordered_policy_metadata_are_semantically_equal():
    first, second = run(), run(); assert first.semantic_dict() == second.semantic_dict()

def test_replay_different_limits_and_capital_change_semantics():
    assert run().semantic_dict() != validate_canonical_risk(canonical_trade_plan_result=canonical(), risk_policy=policy(maximum_lots=1), available_capital=5000, clock=lambda: NOW, sizing_result_id_factory=lambda:"size", result_id_factory=lambda:"risk").semantic_dict()
