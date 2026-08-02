from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1
def test_explicit_policy_requires_existing_values():
 assert LiveCandidatePolicySourceV1("BULLISH","ELIGIBLE",80.,80.).confidence==80.
