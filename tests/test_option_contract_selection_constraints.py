from tests.test_option_contract_selection_input_v1 import _i
from tests.test_trade_planning_policy_v1 import _p
from services.trade_planning import resolve_option_contract_selection_constraints
def test_resolves_stricter_values():
 r=resolve_option_contract_selection_constraints(_i(maximum_entry_premium=90.,minimum_open_interest=5),_p(maximum_entry_premium=100.,minimum_open_interest=3));assert r.effective_maximum_entry_premium==90 and r.effective_minimum_open_interest==5 and r.is_coherent
def test_policy_mismatch_incoherent():assert 'CONTRACT_POLICY_MISMATCH' in resolve_option_contract_selection_constraints(_i(policy_id='BAD'),_p()).incoherence_codes
