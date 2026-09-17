from __future__ import annotations
from datetime import date,datetime,timezone,timedelta
import pytest
from services.contracts.final_decision_v1 import FinalDecisionV1,DataHealthSummary,RiskSummary
from services.contracts.trade_plan_v1 import TradePlanV1
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.risk_policy_v1 import RiskPolicyV1
from services.risk.pipeline import validate_canonical_risk

NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def policy(**c):
 v=dict(policy_id="rp",policy_name="p",capital_base=100000,maximum_capital_per_trade=10000,maximum_capital_fraction=1,maximum_risk_per_trade=2000,maximum_risk_fraction=1,minimum_reward_risk_ratio=1.5,maximum_lots=10,maximum_quantity=500,allow_fractional_lots=False,require_stop_loss=True,require_target=True,require_positive_entry=True,require_positive_stop_loss=True,require_positive_target=True,require_stop_below_entry_for_long=True,require_target_above_entry_for_long=True,insufficient_capital_behavior="BLOCK"); v.update(c); return RiskPolicyV1(**v)
def decision(action="BUY",symbol="NIFTY",exchange="NSE"):
 return FinalDecisionV1(snapshot_id="s",decision_id="d",symbol=symbol,exchange=exchange,instrument_type="OPTION",created_at=NOW,market_timestamp=NOW,action=action,authorization_status="ANALYSIS_ONLY",execution_status="NOT_REQUESTED",risk=RiskSummary(risk_status="APPROVED"),data_health=DataHealthSummary(overall_status="VALID",validation_passed=True))
def plan(symbol="NIFTY",exchange="NSE",action="BUY",kind="CALL"):
 return TradePlanV1("p",NOW,"s","a","d","sel","con",symbol,exchange,action,kind,"SYM",date(2026,7,30),25000,50,100,"LAST",90,120,"X","X",NOW,NOW+timedelta(minutes=5),"READY_FOR_RISK",True)
def selected(): return SelectedOptionContractV1("sel",NOW,"s","d","u","con","NIFTY","NSE","BUY","CALL","SYM",None,date(2026,7,30),25000,50,25000,100,"LAST","EARLIEST_ELIGIBLE","NEAREST_ATM",True)
def canonical(status="PLAN_CREATED",p=None):
 d=decision("WAIT") if status=="NO_ACTION" else decision(); p=None if status=="NO_ACTION" else (p or plan()); return CanonicalTradePlanResultV1("tp",NOW,"s","a","d",d,selected() if status=="PLAN_CREATED" else None,p if status=="PLAN_CREATED" else None,status,blockers=("blocked",) if status in {"BLOCKED","INSUFFICIENT_DATA","FAILED"} else ())
def run(**c): return validate_canonical_risk(canonical_trade_plan_result=canonical(),risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"z",result_id_factory=lambda:"r",**c)
@pytest.mark.parametrize("symbol,exchange,action,kind",[("NIFTY","NSE","BUY","CALL"),("NIFTY","NSE","SELL","PUT"),("SENSEX","BSE","BUY","CALL"),("SENSEX","BSE","SELL","PUT")])
def test_supported_plans_map_to_risk_approved(symbol,exchange,action,kind):
 d=decision(action,symbol,exchange); p=plan(symbol,exchange,action,kind); c=CanonicalTradePlanResultV1("tp",NOW,"s","a","d",d,selected() if symbol=="NIFTY" else selected(),p,"PLAN_CREATED")
 assert validate_canonical_risk(canonical_trade_plan_result=c,risk_policy=policy(),clock=lambda:NOW,sizing_result_id_factory=lambda:"z",result_id_factory=lambda:"r").risk_status=="RISK_APPROVED"
@pytest.mark.parametrize("status",["NO_ACTION","BLOCKED","INSUFFICIENT_DATA","FAILED"])
def test_canonical_gates_do_not_size(status):
 result=validate_canonical_risk(canonical_trade_plan_result=canonical(status),risk_policy=policy(),clock=lambda:NOW,result_id_factory=lambda:"r"); assert result.risk_status==("NO_ACTION" if status=="NO_ACTION" else "BLOCKED")
def test_ids_clock_and_semantics_are_deterministic():
 result=run(); assert (result.result_id,result.sizing_result_id,result.created_at)==("r","z",NOW) and result.semantic_dict()==run().semantic_dict()
@pytest.mark.parametrize("available,status",[(100,"INSUFFICIENT_CAPITAL"),(100000,"RISK_APPROVED")])
def test_sizing_outcomes_map(available,status): assert run(available_capital=available).risk_status==status
@pytest.mark.parametrize("requested",list(range(1,21)))
def test_requested_lot_scenarios_remain_deterministically_approved(requested):
 assert run(requested_lots=requested).risk_status=="RISK_APPROVED"
@pytest.mark.parametrize("available",list(range(5000,25000,1000)))
def test_fundable_capital_scenarios_remain_approved(available):
 assert run(available_capital=available).risk_status=="RISK_APPROVED"
@pytest.mark.parametrize("maximum_lots",list(range(1,21)))
def test_policy_lot_limit_scenarios_remain_approved(maximum_lots):
 assert validate_canonical_risk(canonical_trade_plan_result=canonical(),risk_policy=policy(maximum_lots=maximum_lots),clock=lambda:NOW,sizing_result_id_factory=lambda:"z",result_id_factory=lambda:"r").risk_status=="RISK_APPROVED"
def test_inputs_are_not_mutated():
 c=canonical(); rp=policy(); before=(c.to_dict(),rp.to_dict()); run(); assert (c.to_dict(),rp.to_dict())==before
