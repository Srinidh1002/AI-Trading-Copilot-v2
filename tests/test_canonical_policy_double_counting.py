"""The policy receives one immutable contribution per evidence family only."""
from datetime import datetime, timezone
import pytest
from services.analysis.canonical_directional_policy_evaluator import evaluate_canonical_directional_policy
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1, CanonicalEvidenceFamilySetV1

def contribution(family, direction="BULLISH", strength=80, role="DIRECTIONAL"):
 return CanonicalEvidenceFamilyContributionV1(family,role,"AVAILABLE",direction,strength,90,datetime.now(timezone.utc),evidence_ids=(family,))
def evaluate(items): return evaluate_canonical_directional_policy(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),evidence=CanonicalEvidenceFamilySetV1(tuple(items)))

def test_same_technical_aggregate_cannot_be_reintroduced_as_5m_mtf_or_regime_votes():
 technical=contribution("TECHNICAL")
 with pytest.raises(ValueError,match="one contribution"):
  CanonicalEvidenceFamilySetV1((technical,technical))
 assert evaluate((technical,contribution("DERIVATIVES"))).confidence == evaluate((technical,contribution("DERIVATIVES"))).confidence

def test_broader_external_and_volatility_are_non_directional_and_cannot_raise_confidence():
 base=(contribution("TECHNICAL"),contribution("DERIVATIVES"))
 contextual=(CanonicalEvidenceFamilyContributionV1("BROADER_MARKET","CONFIRMATION","AVAILABLE","NEUTRAL",0,90,datetime.now(timezone.utc),evidence_ids=("cross",)),CanonicalEvidenceFamilyContributionV1("EXTERNAL_CONTEXT","INFORMATIONAL","UNAVAILABLE","UNAVAILABLE",0,0,datetime.now(timezone.utc),evidence_ids=("external",)),CanonicalEvidenceFamilyContributionV1("VOLATILITY","INFORMATIONAL","AVAILABLE","NEUTRAL",0,90,datetime.now(timezone.utc),evidence_ids=("atr-bb-vix-iv",)))
 assert evaluate(base).confidence == evaluate(base+contextual).confidence
