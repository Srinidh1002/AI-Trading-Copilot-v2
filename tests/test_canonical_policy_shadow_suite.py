from datetime import datetime, timezone
from services.analysis.canonical_directional_policy_evaluator import evaluate_canonical_directional_policy
from services.analysis.canonical_policy_shadow import compare_canonical_policy_shadow
from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1, CanonicalEvidenceFamilySetV1

def family(name,direction="BULLISH",strength=80,role="DIRECTIONAL",status="AVAILABLE",reasons=()): return CanonicalEvidenceFamilyContributionV1(name,role,status,direction,strength,90,datetime.now(timezone.utc),evidence_ids=(name,),reasons=reasons)
def canonical(*items): return evaluate_canonical_directional_policy(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),evidence=CanonicalEvidenceFamilySetV1(items))
def legacy(direction="BULLISH",confidence=100,score=2): return LiveCandidatePolicySourceV1(direction,"ELIGIBLE",confidence,score)

def test_weak_legacy_unanimity_diverges_for_evidence_sufficiency():
 value=compare_canonical_policy_shadow(canonical(family("TECHNICAL",strength=2),family("DERIVATIVES",strength=2)),legacy())
 assert value.divergence_code=="CANONICAL_EVIDENCE_INSUFFICIENT" and value.to_dict()["legacy_confidence"]==100

def test_strong_aligned_bullish_and_bearish_match():
 for direction in ("BULLISH","BEARISH"):
  assert compare_canonical_policy_shadow(canonical(family("TECHNICAL",direction),family("DERIVATIVES",direction)),legacy(direction,72,72)).matches

def test_derivative_conflict_and_regime_gate_are_machine_readable_divergences():
 conflict=compare_canonical_policy_shadow(canonical(family("TECHNICAL"),family("DERIVATIVES","BEARISH")),legacy())
 gate=compare_canonical_policy_shadow(canonical(family("TECHNICAL"),family("DERIVATIVES"),family("REGIME","NEUTRAL",0,"ENTRY_RESTRICTION","BLOCKED",("REGIME_BLOCKED",))),legacy())
 assert conflict.divergence_code=="CANONICAL_CONTRADICTION"
 assert gate.divergence_code=="CANONICAL_GATE_BLOCKED"
