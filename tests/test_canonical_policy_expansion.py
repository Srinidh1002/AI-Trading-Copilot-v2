from datetime import datetime, timezone
from services.analysis.canonical_directional_policy_evaluator import evaluate_canonical_directional_policy
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilyContributionV1, CanonicalEvidenceFamilySetV1

def item(family,direction="BULLISH",strength=80,quality=90,role="DIRECTIONAL",status="AVAILABLE",reasons=()):
 return CanonicalEvidenceFamilyContributionV1(family,role,status,direction,strength,quality,datetime.now(timezone.utc),evidence_ids=(family,),reasons=reasons)
def policy(*items): return evaluate_canonical_directional_policy(policy_id="p",symbol="NIFTY",exchange="NSE",evaluated_at=datetime.now(timezone.utc),evidence=CanonicalEvidenceFamilySetV1(items))

def test_strong_unanimous_trade_but_weak_unanimous_bull_or_bear_does_not():
 assert policy(item("TECHNICAL"),item("DERIVATIVES")).decision=="TRADE"
 assert policy(item("TECHNICAL",strength=20),item("DERIVATIVES",strength=20)).decision=="NO_TRADE"
 assert policy(item("TECHNICAL","BEARISH",20),item("DERIVATIVES","BEARISH",20)).decision=="NO_TRADE"

def test_mixed_and_missing_technical_are_not_trade_authorities():
 assert policy(item("TECHNICAL"),item("DERIVATIVES","BEARISH")).decision=="NO_TRADE"
 assert policy(item("DERIVATIVES")).decision=="NO_TRADE"

def test_optional_unavailable_is_not_extra_vote_and_gates_block():
 unavailable=item("BROADER_MARKET","UNAVAILABLE",0,0,"INFORMATIONAL","UNAVAILABLE")
 assert policy(item("TECHNICAL"),item("DERIVATIVES"),unavailable).decision=="TRADE"
 contract=item("CONTRACT_QUALITY","NEUTRAL",0,100,"QUALITY_GATE","BLOCKED",("NO_ELIGIBLE_CONTRACT",))
 result=policy(item("TECHNICAL"),item("DERIVATIVES"),contract)
 assert result.decision=="NO_TRADE" and "NO_ELIGIBLE_CONTRACT" in result.blockers
