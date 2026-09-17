"""Restart-safe immutable record of the already evaluated canonical policy."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1, _aware, _unique_tuple

@dataclass(frozen=True, slots=True)
class CanonicalPolicyProvenanceV1:
    policy: CanonicalDirectionalPolicyV1
    family_source_ids: tuple[str,...]
    persisted_at: datetime
    legacy_shadow_reference: str | None=None
    def __post_init__(self):
        if type(self.policy) is not CanonicalDirectionalPolicyV1: raise TypeError("policy")
        object.__setattr__(self,"family_source_ids",_unique_tuple(self.family_source_ids,"family_source_ids"))
        object.__setattr__(self,"persisted_at",_aware(self.persisted_at,"persisted_at"))
    def reconstruct(self)->dict[str,object]:
        p=self.policy
        return {"policy_id":p.policy_id,"policy_version":p.policy_version,"market":(p.symbol,p.exchange),"evaluated_at":p.evaluated_at.isoformat(),"direction":p.direction,"decision":p.decision,"supporting_families":p.supporting_families,"opposing_families":p.opposing_families,"agreement_strength":p.agreement_strength,"evidence_strength":p.evidence_strength,"confidence":p.confidence,"score":p.score,"blockers":p.blockers,"warnings":p.warnings,"contradictions":p.contradictions,"restrictions":p.entry_restrictions,"reasons":p.reasons,"source_evidence_ids":p.source_ids,"family_source_ids":self.family_source_ids}
