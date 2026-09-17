"""Pure comparison artifact for legacy-to-canonical policy migration."""
from __future__ import annotations
from dataclasses import dataclass
from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1

@dataclass(frozen=True, slots=True)
class CanonicalPolicyShadowComparisonV1:
    canonical_policy_id: str
    canonical_direction: str
    legacy_direction: str
    canonical_decision: str
    legacy_eligibility: str
    matches: bool
    differences: tuple[str, ...]
    legacy_confidence: float
    legacy_score: float
    canonical_agreement: float
    canonical_evidence_strength: float
    canonical_confidence: float
    canonical_score: float
    supporting_families: tuple[str, ...]
    opposing_families: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    contradictions: tuple[str, ...]
    restrictions: tuple[str, ...]
    divergence_code: str
    divergence_reason: str

    def to_dict(self) -> dict[str, object]:
        return {"legacy_direction":self.legacy_direction,"legacy_decision":"TRADE" if self.legacy_eligibility=="ELIGIBLE" else "NO_TRADE","legacy_confidence":self.legacy_confidence,"legacy_score":self.legacy_score,"canonical_direction":self.canonical_direction,"canonical_decision":self.canonical_decision,"canonical_directional_agreement":self.canonical_agreement,"canonical_evidence_strength":self.canonical_evidence_strength,"canonical_confidence":self.canonical_confidence,"canonical_score":self.canonical_score,"supporting_families":self.supporting_families,"opposing_families":self.opposing_families,"blockers":self.blockers,"warnings":self.warnings,"contradictions":self.contradictions,"restrictions":self.restrictions,"divergence_code":self.divergence_code,"divergence_reason":self.divergence_reason}

def compare_canonical_policy_shadow(canonical: CanonicalDirectionalPolicyV1, legacy: LiveCandidatePolicySourceV1) -> CanonicalPolicyShadowComparisonV1:
    if type(canonical) is not CanonicalDirectionalPolicyV1 or type(legacy) is not LiveCandidatePolicySourceV1: raise TypeError("typed canonical and legacy policy required")
    expected = "TRADE" if legacy.eligibility == "ELIGIBLE" else "NO_TRADE"
    differences = tuple(name for name, left, right in (("direction", canonical.direction, legacy.direction), ("decision", canonical.decision, expected), ("confidence", canonical.confidence, legacy.confidence), ("score", canonical.score, legacy.score)) if left != right)
    if not differences: code, reason = "MATCH", "legacy and canonical policy agree"
    elif canonical.decision != expected and canonical.confidence < 55: code, reason = "CANONICAL_EVIDENCE_INSUFFICIENT", "family-level evidence strength did not satisfy canonical confidence gate"
    elif canonical.blockers or canonical.entry_restrictions: code, reason = "CANONICAL_GATE_BLOCKED", "canonical blocker or entry restriction prevents trade"
    elif canonical.contradictions: code, reason = "CANONICAL_CONTRADICTION", "canonical evidence families disagree"
    else: code, reason = "CANONICAL_POLICY_DIVERGENCE", "canonical policy differs from legacy authority"
    return CanonicalPolicyShadowComparisonV1(canonical.policy_id, canonical.direction, legacy.direction, canonical.decision, legacy.eligibility, not differences, differences, legacy.confidence, legacy.score, canonical.agreement_strength, canonical.evidence_strength, canonical.confidence, canonical.score, canonical.supporting_families, canonical.opposing_families, canonical.blockers, canonical.warnings, canonical.contradictions, canonical.entry_restrictions, code, reason)
