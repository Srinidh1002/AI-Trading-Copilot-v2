"""Canonical breaking-event model — Section 6.2-6.13, 6.22. Shadow only."""
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Section 6.3 — Event types
EVENT_TYPES = (
    "MILITARY_ESCALATION", "MILITARY_DEESCALATION", "CEASEFIRE",
    "SANCTIONS", "SANCTIONS_REMOVED",
    "TARIFF", "EXPORT_RESTRICTION", "IMPORT_RESTRICTION",
    "SHIPPING_DISRUPTION", "SHIPPING_NORMALIZATION",
    "OIL_SUPPLY_DISRUPTION", "OIL_SUPPLY_RESTORATION",
    "OPEC_UNSCHEDULED_STATEMENT",
    "REFINERY_OUTAGE", "REFINERY_RESTART",
    "PIPELINE_OUTAGE", "PIPELINE_RESTART",
    "LNG_OUTAGE", "LNG_RESTART",
    "PRODUCTION_OUTAGE", "PRODUCTION_RESTART",
    "HURRICANE", "FREEZE_EVENT", "EXTREME_HEAT", "EARTHQUAKE", "NATURAL_DISASTER",
    "EMERGENCY_FED", "EMERGENCY_RBI", "FX_INTERVENTION",
    "EXCHANGE_OUTAGE", "BROKER_OUTAGE", "MARKET_DATA_OUTAGE",
    "REGULATORY_ACTION", "UNKNOWN_BREAKING_EVENT",
)

# Section 6.4 — Source tiers
SOURCE_TIERS = (
    "TIER_1_OFFICIAL", "TIER_2_MAJOR_WIRE", "TIER_3_REPUTABLE_MEDIA",
    "TIER_4_SECONDARY", "TIER_5_UNVERIFIED",
)

# Section 6.5 — Verification states
VERIFICATION_STATES = (
    "UNVERIFIED", "SINGLE_SOURCE", "MULTI_SOURCE_CORROBORATED",
    "OFFICIALLY_CONFIRMED", "DISPUTED", "CORRECTED", "RETRACTED",
    "FALSE_REPORT", "UNRESOLVED",
)

# Section 6.7 — Dedup classifications
DEDUP_CLASSES = ("NEW_EVENT", "DUPLICATE", "UPDATE", "CORRECTION",
                 "RETRACTION", "RELATED_SEPARATE_EVENT")

# Section 6.11 — Freshness
FRESHNESS_STATES = ("CURRENT", "DEVELOPING", "STALE", "RESOLVED", "SUPERSEDED")

# Section 6.12
SEVERITY_LEVELS = ("INFO", "LOW", "MODERATE", "HIGH", "CRITICAL")

# Section 6.13
URGENCY_LEVELS = ("LOW", "MEDIUM", "HIGH", "IMMEDIATE")

# Section 6.17
RELEVANCE_LEVELS = ("VERY_HIGH", "HIGH", "MEDIUM", "LOW", "NONE")

# Section 6.18
THEORETICAL_IMPACTS = ("BULLISH", "BEARISH", "MIXED", "UNCERTAIN")

# Section 6.21
REACTION_STATES = ("CONFIRMED", "PARTIALLY_CONFIRMED", "CONFLICTED",
                   "INCONCLUSIVE", "DATA_UNAVAILABLE")

# Section 6.22
EVENT_STATES = ("DETECTED", "VERIFYING", "DEVELOPING", "CONFIRMED",
                "STABILIZING", "RESOLVED", "DISPUTED", "RETRACTED", "FALSE_REPORT")

# Section 6.23
SHADOW_ACTIONS = ("CONTINUE_NORMAL", "WATCH", "AVOID_NEW_ENTRY_SHADOW",
                  "REDUCE_RISK_SHADOW", "EXIT_RISK_SHADOW")

# Section 6.25
SOURCE_FAILURE_STATES = ("SOURCE_UNAVAILABLE", "AUTH_FAILURE", "RATE_LIMITED",
                         "NETWORK_UNAVAILABLE", "PARSE_FAILED",
                         "TIMESTAMP_INVALID", "PAYLOAD_INVALID")

# Section 6.28 — Freshness policy by event type (seconds)
FRESHNESS_POLICY = {
    "MILITARY_ESCALATION": 24 * 3600,
    "MILITARY_DEESCALATION": 12 * 3600,
    "CEASEFIRE": 24 * 3600,
    "SANCTIONS": 7 * 86400,
    "TARIFF": 7 * 86400,
    "OIL_SUPPLY_DISRUPTION": 12 * 3600,
    "OPEC_UNSCHEDULED_STATEMENT": 24 * 3600,
    "REFINERY_OUTAGE": 6 * 3600,
    "PIPELINE_OUTAGE": 6 * 3600,
    "LNG_OUTAGE": 6 * 3600,
    "PRODUCTION_OUTAGE": 6 * 3600,
    "HURRICANE": 24 * 3600,
    "FREEZE_EVENT": 24 * 3600,
    "EARTHQUAKE": 12 * 3600,
    "EMERGENCY_FED": 12 * 3600,
    "EMERGENCY_RBI": 12 * 3600,
    "EXCHANGE_OUTAGE": 2 * 3600,
    "BROKER_OUTAGE": 1 * 3600,
    "MARKET_DATA_OUTAGE": 1 * 3600,
    "REGULATORY_ACTION": 7 * 86400,
    "UNKNOWN_BREAKING_EVENT": 3600,
}


def _hash(payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, sort_keys=True, default=str)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def utc_now_iso():
    return datetime.now(UTC).isoformat()


def make_breaking_event(
    event_type, headline, source_name, source_tier,
    source_published_at_iso, received_at_iso=None,
    occurrence_at_iso=None,
    event_cluster_id=None,
    entities=None, countries=None, regions=None,
    infrastructure=None, companies=None, commodities=None,
    affected_products=None,
    severity="INFO", urgency="LOW",
    theoretical_impact="UNCERTAIN",
    theoretical_channels=None,
    source_type="WIRE", source_url=None,
    verification_status="UNVERIFIED",
    status="DETECTED",
    raw_payload=None,
):
    """Build a canonical BreakingEventV1."""
    if event_type not in EVENT_TYPES:
        event_type = "UNKNOWN_BREAKING_EVENT"
    if source_tier not in SOURCE_TIERS:
        source_tier = "TIER_5_UNVERIFIED"
    if verification_status not in VERIFICATION_STATES:
        verification_status = "UNVERIFIED"
    if severity not in SEVERITY_LEVELS:
        severity = "INFO"
    if urgency not in URGENCY_LEVELS:
        urgency = "LOW"
    if theoretical_impact not in THEORETICAL_IMPACTS:
        theoretical_impact = "UNCERTAIN"
    if status not in EVENT_STATES:
        status = "DETECTED"

    now_iso = received_at_iso or utc_now_iso()
    eid = f"BE_{event_type}_{_hash(headline)[:12]}"

    return {
        "event_id": eid,
        "event_cluster_id": event_cluster_id,
        "event_version": 1,
        "event_type": event_type,
        "event_subtype": None,
        "headline": headline,
        "normalized_summary": None,
        "occurrence_time": occurrence_at_iso or "UNKNOWN",
        "source_published_at": source_published_at_iso,
        "first_seen_at": now_iso,
        "received_at": now_iso,
        "last_updated_at": now_iso,
        "source_name": source_name,
        "source_type": source_type,
        "source_url": source_url,
        "source_tier": source_tier,
        "source_reliability": None,
        "verification_status": verification_status,
        "entities": entities or [],
        "countries": countries or [],
        "regions": regions or [],
        "infrastructure": infrastructure or [],
        "companies": companies or [],
        "commodities": commodities or [],
        "affected_products": affected_products or [],
        "severity": severity,
        "urgency": urgency,
        "geographic_scope": None,
        "expected_duration": None,
        "theoretical_impact": theoretical_impact,
        "theoretical_channels": theoretical_channels or [],
        "observed_market_reaction": None,
        "status": status,
        "supersedes_event_version": None,
        "correction_of": None,
        "retraction_of": None,
        "raw_payload_hash": _hash(raw_payload) if raw_payload is not None else None,
        "parser_version": "v1",
        "shadow_only": True,
        "trade_influence": False,
    }


def normalize_headline(headline):
    """Deterministic normalization for dedup comparison."""
    if not headline:
        return ""
    return " ".join(str(headline).lower().split()).strip()


def freshness_status(event, now_iso=None):
    """Section 6.11 — CURRENT / DEVELOPING / STALE / RESOLVED / SUPERSEDED."""
    if event.get("status") in ("RESOLVED", "RETRACTED", "FALSE_REPORT"):
        return "RESOLVED" if event["status"] == "RESOLVED" else "SUPERSEDED"
    try:
        pub = datetime.fromisoformat(event.get("source_published_at") or "")
    except Exception:
        return "STALE"
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=UTC)
    now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(UTC)
    age = (now - pub).total_seconds()
    policy = FRESHNESS_POLICY.get(event.get("event_type"), 3600)
    if age > policy * 2:
        return "STALE"
    if age > policy:
        return "DEVELOPING"
    return "CURRENT"


if __name__ == "__main__":
    e = make_breaking_event(
        "OIL_SUPPLY_DISRUPTION", "Test pipeline reported shut",
        "TEST_SOURCE", "TIER_2_MAJOR_WIRE",
        "2026-09-12T10:00:00+00:00",
        countries=["IRQ"], commodities=["CRUDE"],
        affected_products=["CRUDEOILM"],
        severity="HIGH", urgency="HIGH",
        theoretical_impact="BULLISH",
    )
    print(e["event_id"])
    print("verify:", e["verification_status"], "severity:", e["severity"])
