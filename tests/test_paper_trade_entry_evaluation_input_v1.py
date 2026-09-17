from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import pytest
from services.contracts import PaperTradeEntryEvaluationInputV1
from tests.p7_fixture_helpers import NOW, make_integrated, make_observation, make_policy, make_state

def make_input(**changes):
    values = dict(integrated_trade_plan_result=make_integrated(), lifecycle_policy=make_policy(), lifecycle_state=make_state(), observation=make_observation(), evaluation_timestamp=NOW, requested_transition_id="transition-1", position_id="position-1", entry_fill_id="fill-1")
    values.update(changes); return PaperTradeEntryEvaluationInputV1(**values)

@pytest.mark.parametrize("state", ("PLANNED", "WAITING_FOR_ENTRY"))
def test_accepts_real_ready_plan_and_entry_eligible_state(state): assert make_input(lifecycle_state=make_state(current_state=state)).lifecycle_state.current_state == state
@pytest.mark.parametrize("name", ("integrated_trade_plan_result", "lifecycle_policy", "lifecycle_state", "observation"))
def test_requires_exact_contract_types(name):
    with pytest.raises(TypeError): make_input(**{name: {}})
@pytest.mark.parametrize("status", ("BLOCKED", "NO_SIZE"))
def test_rejects_non_ready_plan(status):
    with pytest.raises(ValueError): make_input(integrated_trade_plan_result=make_integrated(status=status))
@pytest.mark.parametrize("state", ("OPEN", "PARTIALLY_EXITED", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED"))
def test_rejects_non_entry_states(state):
    values = dict(previous_state="WAITING_FOR_ENTRY", transition_sequence=2, is_terminal=state.startswith("CLOSED") or state in {"CANCELLED", "BLOCKED"})
    if state.startswith("CLOSED"): values.update(closed_at=NOW, terminal_reason="TEST")
    if state == "CANCELLED": values.update(cancelled_at=NOW, terminal_reason="TEST")
    if state == "BLOCKED": values.update(blocked_at=NOW, terminal_reason="TEST", blockers=("TEST",))
    with pytest.raises(ValueError): make_input(lifecycle_state=make_state(current_state=state, **values))
@pytest.mark.parametrize("factory,field", ((make_state,"trade_plan_id"),(make_state,"integrated_trade_plan_result_id"),(make_state,"lifecycle_policy_id"),(make_observation,"trade_plan_id"),(make_observation,"integrated_trade_plan_result_id"),(make_observation,"selected_option_contract_id")))
def test_identity_mismatch_rejected(factory, field):
    with pytest.raises(ValueError): make_input(**({"lifecycle_state" if factory is make_state else "observation": factory(**{field:"other"})}))
@pytest.mark.parametrize("field", ("requested_transition_id", "position_id", "entry_fill_id"))
def test_blank_identifiers_rejected(field):
    with pytest.raises(ValueError): make_input(**{field:" "})
def test_naive_time_metadata_serialization_and_frozen_contract():
    with pytest.raises(ValueError): make_input(evaluation_timestamp=datetime(2026,1,8,9,30))
    value=make_input(metadata={"nested":{"items":[1]}}); output=value.to_dict(); output["metadata"]["nested"]["items"].append(2)
    assert value.to_json()==value.to_json() and value.to_dict()["metadata"]=={"nested":{"items":[1]}}
    with pytest.raises(FrozenInstanceError): value.position_id="other"
