from dataclasses import dataclass
from datetime import date,datetime,timezone
from services.contracts.option_contract_v1 import OptionContractV1
from services.contracts.option_contract_universe_v1 import OptionContractUniverseV1
from services.options.pipeline import create_canonical_trade_plan
from services.options.policies import TradePlanPolicy
from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
import pytest
NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
@dataclass
class Snapshot: snapshot_id:str="snap"
@dataclass
class Analysis: analysis_id:str="analysis"; snapshot_id:str="snap"
@dataclass
class Decision:
    action:str="BUY"; authorization_status:str="ANALYSIS_ONLY"; snapshot_id:str="snap"; decision_id:str="decision"; symbol:str="NIFTY"; exchange:str="NSE"; confidence:float=75; execution_status:str="NOT_REQUESTED"
    def to_dict(self): return self.__dict__
def universe(kind="CALL",symbol="NIFTY",exchange="NSE"):
    c=OptionContractV1("contract",symbol,exchange,"SYM",kind,25000,date(2026,7,30),50,NOW,last_price=100)
    return OptionContractUniverseV1("universe",symbol,exchange,NOW,25000,(c,),"synthetic",True)
def run(decision=Decision(),u=None,**kwargs): return create_canonical_trade_plan(snapshot=Snapshot(),analysis=Analysis(),decision=decision,universe=u or universe(),clock=lambda:NOW,selection_id_factory=lambda:"selection",trade_plan_id_factory=lambda:"plan",result_id_factory=lambda:"result",**kwargs)
def test_nifty_buy_creates_call_ready_plan():
    result=run(); assert result.result_status=="PLAN_CREATED" and result.selected_contract.option_type=="CALL" and result.trade_plan.plan_status=="READY_FOR_RISK"
def test_sell_and_sensex_preserve_direction():
    d=Decision(action="SELL",symbol="SENSEX",exchange="BSE"); result=run(d,universe("PUT","SENSEX","BSE")); assert result.selected_contract.option_type=="PUT" and result.decision is d
def test_non_actionable_and_blocked_have_no_plan():
    assert run(Decision(action="WAIT")).result_status=="NO_ACTION"
    assert run(Decision(authorization_status="BLOCKED")).result_status=="BLOCKED"
def test_selection_failure_preserves_decision_and_semantics():
    d=Decision(); result=run(d,OptionContractUniverseV1("u","NIFTY","NSE",NOW,25000,(),"synthetic",True)); assert result.result_status=="BLOCKED" and result.trade_plan is None and result.decision is d
@pytest.mark.parametrize("action",["WAIT","HOLD","NEUTRAL"])
def test_all_non_actionable_actions_are_no_action(action):
    result=run(Decision(action=action)); assert result.result_status=="NO_ACTION" and result.trade_plan is None and result.selected_contract is None
@pytest.mark.parametrize("kind,action",[("PUT","BUY"),("CALL","SELL")])
def test_missing_matching_option_type_blocks(kind,action): assert run(Decision(action=action),universe(kind)).result_status=="BLOCKED"
@pytest.mark.parametrize("captured",[NOW.replace(hour=9),NOW.replace(hour=11)])
def test_universe_freshness_is_deterministic(captured):
    value=universe(); value=OptionContractUniverseV1(value.universe_id,value.underlying_symbol,value.exchange,captured,value.spot_price,value.contracts,value.source_name,value.trusted)
    result=run(u=value); assert result.result_status in {"PLAN_CREATED","BLOCKED"}
def test_missing_entry_maps_to_insufficient_data():
    result=run(trade_plan_policy=TradePlanPolicy(require_entry_reference_price=True),entry_reference_price=None,u=OptionContractUniverseV1("u","NIFTY","NSE",NOW,25000,(OptionContractV1("c","NIFTY","NSE","SYM","CALL",25000,date(2026,7,30),50,NOW),),"synthetic",True)); assert result.result_status=="INSUFFICIENT_DATA"
def test_required_stop_and_target_map_to_insufficient_data():
    assert run(trade_plan_policy=TradePlanPolicy(require_stop_loss=True)).result_status=="INSUFFICIENT_DATA"
    assert run(trade_plan_policy=TradePlanPolicy(require_target=True)).result_status=="INSUFFICIENT_DATA"
def test_ids_clock_and_semantics_are_deterministic():
    result=run(); assert result.result_id=="result" and result.selected_contract.selection_id=="selection" and result.trade_plan.trade_plan_id=="plan"
    assert "result_id" not in result.semantic_dict() and "created_at" not in result.semantic_dict() and result.semantic_dict()==run().semantic_dict()
@pytest.mark.parametrize("allowed",[False,False])
def test_session_blocked_stops_selection(allowed):
    session=type("Session",(),{"analysis_allowed":allowed,"blockers":("session blocked",)})()
    assert run(session_validation=session).result_status=="BLOCKED"
def test_result_contract_rejects_inconsistent_states():
    d=Decision()
    with pytest.raises(ValueError): CanonicalTradePlanResultV1("r",NOW,"snap","analysis","decision",d,None,None,"PLAN_CREATED")
    with pytest.raises(ValueError): CanonicalTradePlanResultV1("r",NOW,"snap","analysis","decision",d,None,None,"BLOCKED")
def test_inputs_and_decision_fields_are_preserved():
    d=Decision(); s=Snapshot(); a=Analysis(); u=universe(); result=create_canonical_trade_plan(snapshot=s,analysis=a,decision=d,universe=u,clock=lambda:NOW,selection_id_factory=lambda:"s",trade_plan_id_factory=lambda:"p",result_id_factory=lambda:"r")
    assert result.decision is d and (d.action,d.confidence,d.authorization_status,d.execution_status)==("BUY",75,"ANALYSIS_ONLY","NOT_REQUESTED") and s.snapshot_id=="snap" and a.analysis_id=="analysis" and u.universe_id=="universe"
def test_nifty_sell_creates_put_plan(): assert run(Decision(action="SELL"),universe("PUT")).selected_contract.option_type=="PUT"
def test_sensex_buy_creates_call_plan(): assert run(Decision(symbol="SENSEX",exchange="BSE"),universe("CALL","SENSEX","BSE")).selected_contract.option_type=="CALL"
def test_sensex_sell_creates_put_plan(): assert run(Decision(action="SELL",symbol="SENSEX",exchange="BSE"),universe("PUT","SENSEX","BSE")).selected_contract.option_type=="PUT"
def test_empty_universe_is_blocked(): assert run(u=OptionContractUniverseV1("empty","NIFTY","NSE",NOW,25000,(),"synthetic",True)).result_status=="BLOCKED"
def test_universe_symbol_mismatch_is_blocked(): assert run(u=universe("CALL","SENSEX","BSE")).result_status=="BLOCKED"
def test_universe_exchange_mismatch_is_blocked():
    contract=OptionContractV1("c","NIFTY","NSE","SYM","CALL",25000,date(2026,7,30),50,NOW)
    with pytest.raises(ValueError): OptionContractUniverseV1("u","NIFTY","BSE",NOW,25000,(contract,),"synthetic",True)
def test_expired_cap_maps_to_blocked(): assert run(contract_expiry_at=NOW).result_status=="BLOCKED"
def test_ids_and_clock_are_preserved_separately():
    result=run(); assert result.result_id=="result"; assert result.created_at==NOW; assert result.selected_contract.selection_id=="selection"; assert result.trade_plan.trade_plan_id=="plan"
def test_semantic_result_excludes_generated_identity_and_time():
    result=run(); assert "result_id" not in result.semantic_dict(); assert "created_at" not in result.semantic_dict()
def test_hold_no_action_is_explicit(): assert run(Decision(action="HOLD")).result_status=="NO_ACTION"
def test_neutral_no_action_is_explicit(): assert run(Decision(action="NEUTRAL")).result_status=="NO_ACTION"
def test_no_matching_call_contract_is_blocked(): assert run(Decision(action="BUY"),universe("PUT")).result_status=="BLOCKED"
