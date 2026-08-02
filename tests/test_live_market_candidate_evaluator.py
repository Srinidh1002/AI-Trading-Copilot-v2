from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1
def test_explicit_policy_requires_existing_values():
 assert LiveCandidatePolicySourceV1("BULLISH","ELIGIBLE",80.,80.).confidence==80.

def test_unavailable_policy_uses_composer_defined_fail_closed_zero():
 value=LiveCandidatePolicySourceV1.unavailable()
 assert (value.direction,value.eligibility,value.confidence,value.score)==("UNAVAILABLE","UNAVAILABLE",0.0,0.0)
 assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" in value.blockers
