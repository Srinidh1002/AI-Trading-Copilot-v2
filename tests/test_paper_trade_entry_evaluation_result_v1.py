from dataclasses import FrozenInstanceError, replace
import pytest
from services.contracts import PaperTradeEntryEvaluationResultV1
from services.paper_trading import evaluate_paper_trade_entry
from tests.p7_fixture_helpers import NOW, make_entry_input, make_observation, make_policy

def result_for(kind):
    if kind == "OPEN": return evaluate_paper_trade_entry(make_entry_input(observation=make_observation(option_open=100., option_high=101., option_low=99., option_close=100.)))
    if kind == "BLOCKED": return evaluate_paper_trade_entry(make_entry_input(observation=make_observation(data_quality_status="INVALID")))
    if kind == "WAITING_FOR_ENTRY": return evaluate_paper_trade_entry(make_entry_input(observation=make_observation(option_last_price=110., option_open=110., option_high=111., option_low=109., option_close=110.)))
    if kind == "CLOSED_SESSION": return evaluate_paper_trade_entry(make_entry_input(observation=make_observation(session_state="CLOSED", is_market_open=False)))
    timestamp=NOW.replace(day=29); return evaluate_paper_trade_entry(make_entry_input(evaluation_timestamp=timestamp,observation=replace(make_observation(),observed_at=timestamp,received_at=timestamp)))

@pytest.mark.parametrize("kind,decision,state", [("BLOCKED","BLOCK","BLOCKED"),("WAITING_FOR_ENTRY","WAIT","PLANNED"),("OPEN","ACTIVATE","OPEN"),("CLOSED_SESSION","SESSION_CLOSE","CLOSED_SESSION"),("CLOSED_EXPIRY","EXPIRY_CLOSE","CLOSED_EXPIRY")])
def test_valid_status_decision_matrix(kind, decision, state):
    value=result_for(kind); assert (value.status,value.entry_decision,value.resulting_lifecycle_state)==(kind,decision,state)
    if kind=="OPEN": assert value.entry_activated and value.position and value.entry_fill and value.position.entry_fill==value.entry_fill and value.entry_fill.observation_id==value.observation_id
    else: assert not value.entry_activated and value.position is None and value.entry_fill is None

@pytest.mark.parametrize("kind,changes", [("BLOCKED",dict(blockers=())), ("WAITING_FOR_ENTRY",dict(blockers=("X",))), ("WAITING_FOR_ENTRY",dict(decision_reasons=())), ("OPEN",dict(entry_activated=False)), ("OPEN",dict(blockers=("X",))), ("CLOSED_EXPIRY",dict(resulting_lifecycle_state="OPEN"))])
def test_status_invariants_reject_invalid_combinations(kind, changes):
    with pytest.raises((ValueError,TypeError)): replace(result_for(kind), **changes)

@pytest.mark.parametrize("kind", ("BLOCKED","WAITING_FOR_ENTRY","OPEN","CLOSED_EXPIRY"))
def test_serialization_is_deterministic_detached_and_frozen(kind):
    value=result_for(kind); first=value.to_dict(); second=value.to_dict(); assert first==second==value.to_dict() and value.to_json()==value.to_json() and value.semantic_dict()==value.semantic_dict()
    first["metadata"]["new"]="mutated"; first["warnings"].append("MUTATED"); assert "new" not in value.to_dict()["metadata"] and "MUTATED" not in value.warnings
    if value.entry_fill: first["entry_fill"]["fill_id"]="mutated"; assert value.entry_fill.fill_id=="fill-1"
    if value.position: first["position"]["position_id"]="mutated"; assert value.position.position_id=="position-1"
    with pytest.raises(FrozenInstanceError): value.status="OPEN"

def test_result_export(): assert PaperTradeEntryEvaluationResultV1
