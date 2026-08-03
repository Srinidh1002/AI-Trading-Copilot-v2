from services.certification.task2_decision_certification_scenarios import get_task2_decision_certification_scenarios
from services.certification.task2_decision_certification_matrix import run_task2_decision_certification_scenario
import pytest
EXPECTED=("NIFTY_CALL_WINS","NIFTY_PUT_WINS","SENSEX_CALL_WINS","SENSEX_PUT_WINS","BOTH_WAIT","WAIT_AND_UNAVAILABLE","BOTH_UNAVAILABLE","ONE_UNAVAILABLE_OTHER_CALL","ONE_UNAVAILABLE_OTHER_PUT","EQUAL_SCORE_CONFIDENCE_TIE","HIGHER_SCORE_WINS","SCORE_TIE_HIGHER_CONFIDENCE_WINS","CONFLICTING_CHILD","REQUIRED_EVIDENCE_MISSING","OPTIONAL_EXTERNAL_UNAVAILABLE","REGIME_BLOCKED","GROUPED_PILLAR_PROVENANCE","CONFIDENCE_LEDGER_DUPLICATE_INPUT","SELECTED_ACTION_INVARIANT_FAILURE")
def test_catalog_is_ordered_fixed_and_identity_coherent():
 values=get_task2_decision_certification_scenarios()
 assert tuple(x.scenario_id for x in values)==EXPECTED
 assert len({x.scenario_id for x in values})==19
 for x in values:
  assert x.fixed_evaluated_at.tzinfo is not None
  assert x.nifty.parent_cycle_id==x.sensex.parent_cycle_id==x.parent_cycle_id
  assert x.nifty.candidate_id!=x.sensex.candidate_id and x.nifty.observation_id!=x.sensex.observation_id
  assert (x.nifty.underlying_symbol,x.nifty.exchange)==("NIFTY","NSE") and (x.sensex.underlying_symbol,x.sensex.exchange)==("SENSEX","BSE")

@pytest.mark.parametrize("scenario,nifty,sensex,selected,parent,status",(
 ("NIFTY_CALL_WINS","CALL","WAIT","NIFTY","CALL","SELECTED"),("NIFTY_PUT_WINS","PUT","WAIT","NIFTY","PUT","SELECTED"),("SENSEX_CALL_WINS","WAIT","CALL","SENSEX","CALL","SELECTED"),("SENSEX_PUT_WINS","WAIT","PUT","SENSEX","PUT","SELECTED"),("BOTH_WAIT","WAIT","WAIT","NONE","NO_TRADE","NO_TRADE"),("WAIT_AND_UNAVAILABLE","WAIT","UNAVAILABLE","NONE","NO_TRADE","NO_TRADE"),("BOTH_UNAVAILABLE","UNAVAILABLE","UNAVAILABLE","NONE","NO_TRADE","NO_TRADE"),("ONE_UNAVAILABLE_OTHER_CALL","UNAVAILABLE","CALL","SENSEX","CALL","SELECTED"),("ONE_UNAVAILABLE_OTHER_PUT","UNAVAILABLE","PUT","SENSEX","PUT","SELECTED"),("EQUAL_SCORE_CONFIDENCE_TIE","CALL","CALL","NIFTY","CALL","SELECTED"),("HIGHER_SCORE_WINS","CALL","CALL","SENSEX","CALL","SELECTED"),("SCORE_TIE_HIGHER_CONFIDENCE_WINS","CALL","CALL","SENSEX","CALL","SELECTED"),("CONFLICTING_CHILD","UNAVAILABLE","WAIT","NONE","NO_TRADE","NO_TRADE"),("REQUIRED_EVIDENCE_MISSING","UNAVAILABLE","WAIT","NONE","NO_TRADE","NO_TRADE"),("OPTIONAL_EXTERNAL_UNAVAILABLE","WAIT","WAIT","NONE","NO_TRADE","NO_TRADE"),("REGIME_BLOCKED","UNAVAILABLE","WAIT","NONE","NO_TRADE","NO_TRADE"),("GROUPED_PILLAR_PROVENANCE","CALL","WAIT","NIFTY","CALL","SELECTED"),("CONFIDENCE_LEDGER_DUPLICATE_INPUT","CALL","WAIT","NIFTY","CALL","SELECTED"),("SELECTED_ACTION_INVARIANT_FAILURE","WAIT","WAIT","NONE","NO_TRADE","NO_TRADE")))
def test_every_scenario_has_the_expected_production_outcome(scenario,nifty,sensex,selected,parent,status):
 result=run_task2_decision_certification_scenario(scenario)
 assert (result.nifty.pre_entry_action,result.sensex.pre_entry_action,result.selected_market,result.parent_action,result.parent_decision_status,result.invariant_status,result.certification_status)==(nifty,sensex,selected,parent,status,"VALID","PASS")
 assert result.nifty.pillar_contribution_count==result.sensex.pillar_contribution_count==14
