"""Provider-free explanation of a persisted policy, never a new recommendation."""
from services.contracts.canonical_policy_provenance_v1 import CanonicalPolicyProvenanceV1
def reconstruct_canonical_recommendation(provenance: CanonicalPolicyProvenanceV1)->dict[str,object]:
    if type(provenance) is not CanonicalPolicyProvenanceV1: raise TypeError("provenance")
    result=provenance.reconstruct(); result["reconstruction_mode"]="PERSISTED_ONLY"; result["contract_eligibility"]="NOT_RECONSTRUCTED"; result["risk_disposition"]="NOT_RECONSTRUCTED"; return result
