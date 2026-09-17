from datetime import datetime, timezone
import json
import pytest
from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.market_regime import evaluate_market_regime
from tests.fixtures.p5_10j_market_regime_replay import IDENTITIES, input_for
TS=datetime(2026,1,1,tzinfo=timezone.utc)
def make_candidate(identity=IDENTITIES[0], **changes):
 inp=input_for(identity,identifier="candidate")
 v=dict(candidate_id="candidate",evaluated_at=TS,underlying_symbol=identity[0],exchange=identity[1],market_regime=evaluate_market_regime(inp),market_session_validation=inp.market_session_validation,candidate_status="READY",analysis_allowed=True,new_entries_allowed=True,opportunity_confidence=0.,regime_suitability_score=.8,technical_confirmation_score=.8,option_chain_confirmation_score=0.,broader_market_confirmation_score=0.,external_context_confirmation_score=0.,data_quality_score=.8,liquidity_score=0.,execution_quality_score=0.,trade_opportunity_available=False,option_chain_available=False,broader_market_available=False,external_context_available=False,liquidity_available=False,execution_quality_available=False,entry_restriction_state="OPEN",data_quality_state="GOOD",freshness_state="FRESH")
 v.update(changes); return MarketOpportunityCandidateV1(**v)
def test_candidate_is_frozen_json_safe_and_immutable():
 c=make_candidate(source_timestamps={"A":TS},metadata={"nested":{"x":1}})
 assert c.to_dict()==c.to_dict() and json.loads(c.to_json())["candidate_id"]=="candidate"
 with pytest.raises(Exception): c.candidate_id="x"
 with pytest.raises(TypeError): c.source_timestamps["B"]=TS
 with pytest.raises(TypeError): c.metadata["nested"]["x"]=2
@pytest.mark.parametrize("field",("opportunity_confidence","regime_suitability_score","technical_confirmation_score","option_chain_confirmation_score","broader_market_confirmation_score","external_context_confirmation_score","data_quality_score","liquidity_score","execution_quality_score"))
@pytest.mark.parametrize("value",(-.1,1.1,True,None,"x",float("nan"),float("inf"),float("-inf")))
def test_scores_are_bounded(field,value):
 with pytest.raises(ValueError): make_candidate(**{field:value})
def test_status_coherence_and_paper_only():
 with pytest.raises(ValueError): make_candidate(warnings=("W",))
 assert make_candidate(candidate_status="READY_WITH_WARNINGS",warnings=("W",)).warnings==("W",)
 assert make_candidate(candidate_status="CONFLICTING",contradictions=("C",)).candidate_status=="CONFLICTING"
 assert make_candidate(candidate_status="BLOCKED",new_entries_allowed=False,blockers=("B",)).candidate_status=="BLOCKED"
 with pytest.raises(ValueError): make_candidate(execution_mode="LIVE")
