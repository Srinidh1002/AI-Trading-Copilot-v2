"""P3-5E fail-open audit tests; all inputs are synthetic and in-memory."""
from datetime import date, datetime, timedelta, timezone
import inspect
import pytest

from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.contracts.trade_plan_v1 import TradePlanV1
from services.contracts.final_decision_v1 import DataHealthSummary, FinalDecisionV1, RiskSummary
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
from services.observability import AuditEmitter, InMemoryAuditSink
from services.risk import calculate_position_size
from services.risk.pipeline import validate_canonical_risk
from services.paper.paper_candidate_service import prepare_paper_candidate

NOW = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)
def policy(**c):
    values=dict(policy_id="p",policy_name="p",capital_base=100000,maximum_capital_per_trade=10000,maximum_capital_fraction=1,maximum_risk_per_trade=2000,maximum_risk_fraction=1,minimum_reward_risk_ratio=1.5,maximum_lots=10,maximum_quantity=500,allow_fractional_lots=False,require_stop_loss=True,require_target=True,require_positive_entry=True,require_positive_stop_loss=True,require_positive_target=True,require_stop_below_entry_for_long=True,require_target_above_entry_for_long=True,insufficient_capital_behavior="BLOCK"); values.update(c); return RiskPolicyV1(**values)
def plan(**c):
    values=dict(trade_plan_id="plan",created_at=NOW,snapshot_id="snap",analysis_id="analysis",decision_id="decision",selection_id="selection",contract_id="contract",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",trading_symbol="OPT",expiry_date=date(2026,7,30),strike=25000,lot_size=50,entry_reference_price=100,entry_price_source="LAST",stop_loss_price=90,target_price=120,stop_loss_source="EXPLICIT",target_source="EXPLICIT",valid_from=NOW,valid_until=NOW+timedelta(minutes=5),plan_status="READY_FOR_RISK",paper_preparation_eligible=True); values.update(c); return TradePlanV1(**values)
def events(**c):
    sink=InMemoryAuditSink(); result=calculate_position_size(trade_plan=plan(**c),risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"size",audit_emitter=AuditEmitter(sink)); return result,sink.events
def approved_canonical_risk(action):
    option_type = "CALL" if action == "BUY" else "PUT"; p = plan(action=action, option_type=option_type)
    decision = FinalDecisionV1(snapshot_id="snap",decision_id="decision",symbol="NIFTY",exchange="NSE",instrument_type="OPTION",created_at=NOW,market_timestamp=NOW,action=action,authorization_status="ANALYSIS_ONLY",execution_status="NOT_REQUESTED",risk=RiskSummary(risk_status="APPROVED"),data_health=DataHealthSummary(overall_status="VALID",validation_passed=True))
    selected = SelectedOptionContractV1("selection",NOW,"snap","decision","universe","contract","NIFTY","NSE",action,option_type,"OPT",None,p.expiry_date,p.strike,p.lot_size,p.strike,100,"LAST","EARLIEST_ELIGIBLE","NEAREST_ATM",True)
    source = CanonicalTradePlanResultV1("trade-result",NOW,"snap","analysis","decision",decision,selected,p,"PLAN_CREATED")
    return decision, validate_canonical_risk(canonical_trade_plan_result=source,risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"size",result_id_factory=lambda:"risk")
class BrokenEmitter:
    def emit(self, event): raise RuntimeError("audit unavailable")

def test_sizing_default_noop_and_fail_open_preserve_result():
    baseline=calculate_position_size(trade_plan=plan(),risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"size")
    observed=calculate_position_size(trade_plan=plan(),risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"size",audit_emitter=BrokenEmitter())
    assert baseline == observed

@pytest.mark.parametrize("changes,terminal", [({},"POSITION_SIZING_COMPLETED"),({"plan_status":"BLOCKED","paper_preparation_eligible":False,"blockers":("plan_blocked",)},"POSITION_SIZING_BLOCKED"),({"entry_reference_price":None},"POSITION_SIZING_BLOCKED"),({"valid_from":NOW-timedelta(minutes=10),"valid_until":NOW-timedelta(minutes=1)},"POSITION_SIZING_BLOCKED")])
def test_sizing_emits_started_then_exactly_one_terminal(changes,terminal):
    result, recorded=events(**changes); assert [e.event_type for e in recorded] == ["POSITION_SIZING_STARTED",terminal] and recorded[-1].attributes["sizing_status"] == result.sizing_status

@pytest.mark.parametrize("field", ["snapshot_id","analysis_id","decision_id","symbol","exchange","action","trade_plan_id","sizing_result_id","lot_size","approved_lots","quantity","capital_required","maximum_loss","sizing_status","blocker_count"])
def test_sizing_payload_is_bounded_and_contains_expected_identity(field):
    _, recorded=events(); terminal=recorded[-1]
    assert (getattr(terminal,field) if field in {"snapshot_id","analysis_id","decision_id","symbol","exchange","action"} else terminal.attributes.get(field)) is not None
    assert not {"risk_policy","trade_plan","sizing_result","decision","candidate","snapshot"} & set(terminal.attributes)

def test_risk_pipeline_declares_optional_fail_open_hooks_and_no_sizing_for_gates():
    source=inspect.getsource(validate_canonical_risk)
    assert "audit_emitter=None" in source and "RISK_VALIDATION_STARTED" in source and 'if source.result_status=="NO_ACTION": return result("NO_ACTION")' in source

@pytest.mark.parametrize("action", ["BUY", "SELL"])
def test_canonical_paper_preparation_emits_long_position_side(action):
    decision, risk_result = approved_canonical_risk(action); sink = InMemoryAuditSink()
    preparation = prepare_paper_candidate(decision, canonical_risk_result=risk_result, audit_emitter=AuditEmitter(sink))
    assert preparation.candidate is not None and preparation.candidate.position_side == "LONG"
    assert [event.event_type for event in sink.events] == ["PAPER_PREPARATION_STARTED", "PAPER_PREPARATION_COMPLETED"]
    assert sink.events[-1].attributes["position_side"] == "LONG"
    assert not {"candidate", "paper_candidate", "risk_result", "trade_plan", "decision"} & set(sink.events[-1].attributes)
