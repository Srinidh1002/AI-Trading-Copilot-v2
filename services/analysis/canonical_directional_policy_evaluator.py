"""Deterministic, provider-free canonical policy evaluation from family evidence."""
from __future__ import annotations
from datetime import datetime
from services.contracts.canonical_directional_policy_v1 import CanonicalDirectionalPolicyV1
from services.contracts.canonical_evidence_family_v1 import CanonicalEvidenceFamilySetV1

MIN_CONFIDENCE = 55.0
MIN_DIRECTIONAL_FAMILIES = 2

def evaluate_canonical_directional_policy(*, policy_id: str, symbol: str, exchange: str, evaluated_at: datetime, evidence: CanonicalEvidenceFamilySetV1) -> CanonicalDirectionalPolicyV1:
    """Gate first, then make one family-level decision without rescoring inputs."""
    items = evidence.contributions
    blockers = tuple(reason for item in items if item.status == "BLOCKED" for reason in item.reasons) or tuple(item.family + "_BLOCKED" for item in items if item.status == "BLOCKED")
    technical = next((item for item in items if item.family == "TECHNICAL"), None)
    if technical is None or technical.status != "AVAILABLE" or technical.role != "DIRECTIONAL":
        blockers = blockers + ("MANDATORY_TECHNICAL_UNAVAILABLE",)
    restrictions = tuple(reason for item in items if item.role in {"ENTRY_RESTRICTION", "QUALITY_GATE", "RISK_GATE"} and item.status != "AVAILABLE" for reason in item.reasons)
    directional = tuple(item for item in items if item.role in {"DIRECTIONAL", "CONFIRMATION", "CONTRADICTION"} and item.status == "AVAILABLE" and item.direction in {"BULLISH", "BEARISH"})
    bullish = tuple(item for item in directional if item.direction == "BULLISH")
    bearish = tuple(item for item in directional if item.direction == "BEARISH")
    support, oppose = (bullish, bearish) if sum(x.strength * x.quality for x in bullish) >= sum(x.strength * x.quality for x in bearish) else (bearish, bullish)
    direction = support[0].direction if support else "UNAVAILABLE"
    agreement = (len(support) / len(directional) * 100.0) if directional else 0.0
    confidence = (sum(x.strength * x.quality / 100.0 for x in support) / len(support)) if support else 0.0
    evidence_strength = sum(x.strength for x in directional) / len(directional) if directional else 0.0
    contradictions = tuple(reason for item in oppose for reason in item.reasons) or tuple(item.family + "_OPPOSES" for item in oppose)
    warnings = tuple(reason for item in items if item.status == "UNAVAILABLE" for reason in item.reasons)
    if blockers or restrictions or oppose or len(directional) < MIN_DIRECTIONAL_FAMILIES or confidence < MIN_CONFIDENCE:
        decision = "NO_TRADE"
        if not directional: direction = "UNAVAILABLE"
    else:
        decision = "TRADE"
    return CanonicalDirectionalPolicyV1(policy_id=policy_id, symbol=symbol, exchange=exchange, evaluated_at=evaluated_at, direction=direction, decision=decision, agreement_strength=agreement, evidence_strength=evidence_strength, confidence=confidence, score=confidence, supporting_families=tuple(item.family for item in support), opposing_families=tuple(item.family for item in oppose), blockers=blockers, warnings=warnings, contradictions=contradictions, entry_restrictions=restrictions, reasons=tuple(reason for item in support for reason in item.reasons), source_ids=tuple(source for item in items for source in item.evidence_ids))
