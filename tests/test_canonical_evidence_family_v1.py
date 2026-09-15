from datetime import datetime, timezone
import pytest
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1, CanonicalEvidenceFamilySetV1

def _contribution(**changes):
    values = dict(family="TECHNICAL", role="DIRECTIONAL", status="AVAILABLE", direction="BULLISH", strength=60, quality=80, observed_at=datetime.now(timezone.utc), evidence_ids=("tech-1",)); values.update(changes)
    return CanonicalEvidenceFamilyContributionV1(**values)

def test_duplicate_family_is_rejected():
    item = _contribution()
    with pytest.raises(ValueError, match="one contribution"): CanonicalEvidenceFamilySetV1((item, item))

def test_information_and_gates_cannot_vote_direction():
    with pytest.raises(ValueError): _contribution(role="INFORMATIONAL")
    with pytest.raises(ValueError): _contribution(role="ENTRY_RESTRICTION")

def test_unavailable_cannot_claim_positive_strength_and_restriction_stays_separate():
    with pytest.raises(ValueError): _contribution(status="UNAVAILABLE", direction="UNAVAILABLE", strength=5)
    assert _contribution(role="ENTRY_RESTRICTION", direction="NEUTRAL", status="BLOCKED", strength=0).role == "ENTRY_RESTRICTION"
