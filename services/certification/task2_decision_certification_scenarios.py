"""Ordered, fixed-time Task 2E3 scenario catalog."""
from datetime import datetime,timezone
from services.certification.task2_decision_fixture_factory import market_fixture
from services.contracts.task2_decision_certification_fixture_v1 import Task2TwoMarketFixtureV1
NOW=datetime(2026,8,3,10,tzinfo=timezone.utc)
def _scenario(name,nifty_profile,sensex_profile,selected="NONE",action="NO_TRADE",status=None,nifty_score=75.,sensex_score=75.,nifty_confidence=75.,sensex_confidence=75.):
 parent=f"parent:{name}"
 nifty=market_fixture(profile=nifty_profile,underlying_symbol="NIFTY",exchange="NSE",parent_cycle_id=parent,observation_id=f"observation:{name}:nifty",candidate_id=f"candidate:{name}:nifty",evaluated_at=NOW)
 sensex=market_fixture(profile=sensex_profile,underlying_symbol="SENSEX",exchange="BSE",parent_cycle_id=parent,observation_id=f"observation:{name}:sensex",candidate_id=f"candidate:{name}:sensex",evaluated_at=NOW)
 from dataclasses import replace
 nifty=replace(nifty,candidate_score=nifty_score,candidate_confidence=nifty_confidence);sensex=replace(sensex,candidate_score=sensex_score,candidate_confidence=sensex_confidence)
 return Task2TwoMarketFixtureV1(name,parent,NOW,nifty,sensex,selected,action,status or ("SELECTED" if selected!="NONE" else "NO_TRADE"),"VALID")
SCENARIOS=(
 _scenario("NIFTY_CALL_WINS","ELIGIBLE_BULLISH","VALID_WAIT","NIFTY","CALL"),_scenario("NIFTY_PUT_WINS","ELIGIBLE_BEARISH","VALID_WAIT","NIFTY","PUT"),_scenario("SENSEX_CALL_WINS","VALID_WAIT","ELIGIBLE_BULLISH","SENSEX","CALL"),_scenario("SENSEX_PUT_WINS","VALID_WAIT","ELIGIBLE_BEARISH","SENSEX","PUT"),_scenario("BOTH_WAIT","VALID_WAIT","VALID_WAIT"),_scenario("WAIT_AND_UNAVAILABLE","VALID_WAIT","UNAVAILABLE_CHILD"),_scenario("BOTH_UNAVAILABLE","UNAVAILABLE_CHILD","UNAVAILABLE_CHILD"),_scenario("ONE_UNAVAILABLE_OTHER_CALL","UNAVAILABLE_CHILD","ELIGIBLE_BULLISH","SENSEX","CALL"),_scenario("ONE_UNAVAILABLE_OTHER_PUT","UNAVAILABLE_CHILD","ELIGIBLE_BEARISH","SENSEX","PUT"),_scenario("EQUAL_SCORE_CONFIDENCE_TIE","ELIGIBLE_BULLISH","ELIGIBLE_BULLISH","NIFTY","CALL"),_scenario("HIGHER_SCORE_WINS","ELIGIBLE_BULLISH","ELIGIBLE_BULLISH","SENSEX","CALL",nifty_score=70.,sensex_score=80.),_scenario("SCORE_TIE_HIGHER_CONFIDENCE_WINS","ELIGIBLE_BULLISH","ELIGIBLE_BULLISH","SENSEX","CALL",nifty_confidence=70.,sensex_confidence=80.),_scenario("CONFLICTING_CHILD","CONFLICTING_CHILD","VALID_WAIT"),_scenario("REQUIRED_EVIDENCE_MISSING","REQUIRED_EVIDENCE_MISSING","VALID_WAIT"),_scenario("OPTIONAL_EXTERNAL_UNAVAILABLE","OPTIONAL_EXTERNAL_UNAVAILABLE","VALID_WAIT"),_scenario("REGIME_BLOCKED","REGIME_BLOCKED","VALID_WAIT"),_scenario("GROUPED_PILLAR_PROVENANCE","ELIGIBLE_BULLISH","VALID_WAIT","NIFTY","CALL"),_scenario("CONFIDENCE_LEDGER_DUPLICATE_INPUT","ELIGIBLE_BULLISH","VALID_WAIT","NIFTY","CALL"),_scenario("SELECTED_ACTION_INVARIANT_FAILURE","VALID_WAIT","VALID_WAIT"),)
def get_task2_decision_certification_scenarios():return SCENARIOS
