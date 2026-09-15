from datetime import datetime, timezone
from services.certification.task8_live_candidate_adapter import _policy_source
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1

def _policy():
    return CanonicalDirectionalPolicyV1(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),direction="BULLISH",decision="TRADE",agreement_strength=80,evidence_strength=75,confidence=70,score=65,source_ids=("capture",))

def test_canonical_policy_has_precedence_over_legacy_strategy():
    source = _policy_source({"canonical_directional_policy": _policy(), "strategy": {"direction":"BEARISH", "decision":"TRADE", "direction_confidence":99, "evidence_strength_score":99}}, expected_identity=("NIFTY","NSE"))
    assert source.direction == "BULLISH" and source.score == 65

def test_legacy_is_unavailable_without_explicit_migration_flag():
    strategy={"direction":"BULLISH", "decision":"TRADE", "direction_confidence":70, "evidence_strength_score":60}
    assert _policy_source({"strategy":strategy}, allow_legacy_fallback=False).direction == "UNAVAILABLE"
    assert _policy_source({"strategy":strategy}, allow_legacy_fallback=True).direction == "BULLISH"
