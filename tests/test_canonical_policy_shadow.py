from datetime import datetime, timezone
from services.analysis.canonical_policy_shadow import compare_canonical_policy_shadow
from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1

def test_shadow_comparison_has_no_provider_side_effects_and_explains_difference():
    canonical=CanonicalDirectionalPolicyV1(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),direction="BULLISH",decision="TRADE",agreement_strength=80,evidence_strength=80,confidence=70,score=60,source_ids=("capture",))
    legacy=LiveCandidatePolicySourceV1(direction="BEARISH",eligibility="INELIGIBLE",confidence=50,score=40)
    result=compare_canonical_policy_shadow(canonical, legacy)
    assert not result.matches and set(result.differences) == {"direction","decision","confidence","score"}
