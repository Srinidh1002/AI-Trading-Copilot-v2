from datetime import datetime, timezone
from services.analysis.canonical_directional_policy_evaluator import evaluate_canonical_directional_policy
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1, CanonicalEvidenceFamilySetV1

def _item(family, direction, strength, quality=90, **extra):
    values=dict(family=family,role="DIRECTIONAL",status="AVAILABLE",direction=direction,strength=strength,quality=quality,observed_at=datetime.now(timezone.utc),evidence_ids=(family,)); values.update(extra)
    return CanonicalEvidenceFamilyContributionV1(**values)

def _evaluate(items): return evaluate_canonical_directional_policy(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),evidence=CanonicalEvidenceFamilySetV1(tuple(items)))

def test_weak_unanimous_evidence_does_not_pass_confidence_gate():
    assert _evaluate([_item("TECHNICAL","BULLISH",20),_item("DERIVATIVES","BULLISH",20)]).decision == "NO_TRADE"

def test_blocker_and_restriction_precede_directional_decision():
    restricted = _item("RISK","NEUTRAL",0,role="RISK_GATE",status="BLOCKED",reasons=("RISK_LIMIT",))
    result = _evaluate([_item("TECHNICAL","BULLISH",80),_item("DERIVATIVES","BULLISH",80),restricted])
    assert result.decision == "NO_TRADE" and "RISK_LIMIT" in result.blockers
