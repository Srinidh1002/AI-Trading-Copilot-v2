"""Breaking news source adapters — Section 6.4, 6.25, 6.44, 6.45. Fixture-default."""
import hashlib, json, os
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
import sys
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


class SourceResult:
    def __init__(self, status, payload=None, reason=None, source=None, tier=None,
                 raw_hash=None, fetched_at=None):
        self.status = status
        self.payload = payload
        self.reason = reason
        self.source = source
        self.tier = tier
        self.raw_hash = raw_hash
        self.fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()


# Registry of known sources → tier (Section 6.4)
SOURCE_REGISTRY = {
    "EIA": ("TIER_1_OFFICIAL", "WIRE"),
    "OPEC": ("TIER_1_OFFICIAL", "WIRE"),
    "Federal Reserve": ("TIER_1_OFFICIAL", "WIRE"),
    "US_TREASURY": ("TIER_1_OFFICIAL", "WIRE"),
    "RBI": ("TIER_1_OFFICIAL", "WIRE"),
    "MCX": ("TIER_1_OFFICIAL", "EXCHANGE"),
    "TEST_WIRE_A": ("TIER_2_MAJOR_WIRE", "WIRE"),
    "TEST_WIRE_B": ("TIER_2_MAJOR_WIRE", "WIRE"),
    "TEST_MEDIA": ("TIER_3_REPUTABLE_MEDIA", "MEDIA"),
    "TEST_SOCIAL": ("TIER_5_UNVERIFIED", "SOCIAL"),
    "UNKNOWN": ("TIER_5_UNVERIFIED", "UNKNOWN"),
}


def tier_for(source_name):
    return SOURCE_REGISTRY.get(source_name, ("TIER_5_UNVERIFIED", "UNKNOWN"))


def load_fixture(fixture_name):
    p = f"data/breaking_news/fixtures/{fixture_name}.json"
    if not os.path.exists(p):
        return SourceResult("SOURCE_UNAVAILABLE", reason=f"missing fixture {fixture_name}",
                            source="FIXTURE")
    try:
        with open(p, encoding="utf-8") as f:
            payload = json.load(f)
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return SourceResult("FIXTURE_LOADED", payload=payload, source="FIXTURE",
                            raw_hash=h)
    except Exception as e:
        return SourceResult("PARSE_FAILED", reason=str(e)[:80], source="FIXTURE")


def fetch_live_news(since_iso=None):
    """Live news fetch — not configured. Returns honest status."""
    return SourceResult("SOURCE_UNAVAILABLE",
                        reason="live news provider not configured",
                        source="UNCONFIGURED")


def fetch_event_by_id(event_id):
    """Fixture loader by event_id."""
    return load_fixture(event_id)


if __name__ == "__main__":
    print("SOURCE_REGISTRY entries:", len(SOURCE_REGISTRY))
    print("EIA tier:", tier_for("EIA"))
    print("social tier:", tier_for("TEST_SOCIAL"))
