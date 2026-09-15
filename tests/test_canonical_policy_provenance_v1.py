from datetime import datetime, timezone
from services.analysis.canonical_policy_reconstruction import reconstruct_canonical_recommendation
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1
from services.contracts.canonical_policy_provenance_v1 import CanonicalPolicyProvenanceV1
def test_reconstruction_is_deterministic_and_provider_free():
 p=CanonicalDirectionalPolicyV1(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime(2026,8,13,tzinfo=timezone.utc),direction="BULLISH",decision="TRADE",agreement_strength=80,evidence_strength=70,confidence=70,score=65,source_ids=("technical:t",))
 a=CanonicalPolicyProvenanceV1(p,("technical:t",),datetime.now(timezone.utc))
 assert reconstruct_canonical_recommendation(a)==reconstruct_canonical_recommendation(a)
