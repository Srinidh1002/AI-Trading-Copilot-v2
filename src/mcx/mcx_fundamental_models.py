"""Canonical fundamental observation contract — Section 5.2, 5.25, 5.26, 5.27.
Generic but commodity-aware. No I/O. No fabrication.
"""
import hashlib
import json
from datetime import datetime, timezone

# Allowed statuses (Section 5.2)
STATUS_VALUES = ("AVAILABLE", "NOT_RELEASED", "SOURCE_UNAVAILABLE",
                 "DATA_UNAVAILABLE", "STALE", "PARSE_FAILED", "PERIOD_MISMATCH")

# Product identifiers
PRODUCTS = ("CRUDEOILM", "GOLDM", "NATGASMINI")

# Driver type categories
DRIVER_TYPES = (
    "INVENTORY", "SUPPLY", "DEMAND", "PRICE_STRUCTURE", "POLICY",
    "WEATHER", "FLOW", "YIELD", "FX", "POSITIONING", "MACRO_REF",
)

# Freshness policies per driver category (Section 5.25)
FRESHNESS_POLICIES = {
    "FAST_MARKET":    {"max_age_seconds": 300,   "policy": "seconds-minutes"},
    "WEEKLY_EIA":     {"max_age_seconds": 8 * 86400, "policy": "valid until next release"},
    "DAILY_FLOW":     {"max_age_seconds": 2 * 86400, "policy": "daily reporting period"},
    "MONTHLY_CB":     {"max_age_seconds": 45 * 86400, "policy": "structurally slow-moving"},
    "OPEC_POLICY":    {"max_age_seconds": 90 * 86400, "policy": "valid until superseded"},
    "WEATHER":        {"max_age_seconds": 12 * 3600, "policy": "forecast issue time"},
    "STRUCTURAL":     {"max_age_seconds": 180 * 86400, "policy": "multi-month context"},
}

# Fundamental state classifications (Section 5.37)
FUNDAMENTAL_STATES = ("BULLISH", "BEARISH", "MIXED", "INCONCLUSIVE", "DATA_UNAVAILABLE")

# Failure reasons (Section 5.35)
REASON_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
REASON_WEATHER_DATA_UNAVAILABLE = "WEATHER_DATA_UNAVAILABLE"
REASON_OPEC_DATA_UNAVAILABLE = "OPEC_DATA_UNAVAILABLE"
REASON_ETF_DATA_UNAVAILABLE = "ETF_DATA_UNAVAILABLE"
REASON_EIA_DATA_UNAVAILABLE = "EIA_DATA_UNAVAILABLE"
REASON_STALE_BEYOND_POLICY = "STALE_BEYOND_POLICY"


def _hash(payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, sort_keys=True, default=str)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_observation(product, driver_type, metric_id, reference_period,
                     observation_time_iso, units=None,
                     source=None, source_identifier=None,
                     previous=None, previous_revised=None,
                     consensus=None, consensus_source=None,
                     actual=None, five_year_average=None,
                     freshness_policy="WEEKLY_EIA",
                     release_time_iso=None, source_time_iso=None,
                     importance="MEDIUM", direction=None, magnitude=None,
                     parser_version="v1", raw_payload=None,
                     status="AVAILABLE"):
    """Build a canonical CommodityFundamentalObservationV1."""
    if product not in PRODUCTS:
        raise ValueError(f"UNKNOWN_PRODUCT: {product}")

    avp = None
    if actual is not None and previous is not None:
        try:
            avp = round(float(actual) - float(previous), 6)
        except Exception:
            avp = None

    avc = None
    if actual is not None and consensus is not None:
        try:
            avc = round(float(actual) - float(consensus), 6)
        except Exception:
            avc = None

    dev5 = None
    if actual is not None and five_year_average is not None:
        try:
            dev5 = round(float(actual) - float(five_year_average), 6)
        except Exception:
            dev5 = None

    return {
        "observation_id": f"{product}_{metric_id}_{reference_period}",
        "product": product,
        "driver_type": driver_type,
        "metric_id": metric_id,
        "reference_period": reference_period,
        "observation_time": observation_time_iso,
        "release_time": release_time_iso,
        "source_time": source_time_iso or observation_time_iso,
        "units": units,
        "previous": previous,
        "previous_revised": previous_revised,
        "consensus": consensus,
        "consensus_source": consensus_source,
        "actual": actual,
        "actual_vs_previous": avp,
        "actual_vs_consensus": avc,
        "five_year_average": five_year_average,
        "deviation_from_five_year_average": dev5,
        "direction": direction,
        "magnitude": magnitude,
        "importance": importance,
        "source": source,
        "source_identifier": source_identifier,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_payload_hash": _hash(raw_payload) if raw_payload is not None else None,
        "parser_version": parser_version,
        "freshness_policy": freshness_policy,
        "freshness_seconds": None,
        "status": status,
    }


def compute_freshness(obs, now_iso=None):
    """Return (freshness_seconds, status, stale_reason). Never uses wall-clock for events."""
    if now_iso is None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.fromisoformat(now_iso)
    try:
        src = datetime.fromisoformat(obs.get("source_time") or obs["observation_time"])
    except Exception:
        return None, "DATA_UNAVAILABLE", "unparseable_source_time"
    if src.tzinfo is None:
        src = src.replace(tzinfo=timezone.utc)
    age = (now - src).total_seconds()
    policy = FRESHNESS_POLICIES.get(obs.get("freshness_policy", "WEEKLY_EIA"), {})
    max_age = policy.get("max_age_seconds")
    if max_age is None:
        return int(age), "AVAILABLE", None
    if age > max_age:
        return int(age), "STALE", REASON_STALE_BEYOND_POLICY
    return int(age), "AVAILABLE", None


if __name__ == "__main__":
    o = make_observation(
        product="CRUDEOILM", driver_type="INVENTORY",
        metric_id="COMMERCIAL_CRUDE_STOCKS",
        reference_period="2026-W36",
        observation_time_iso="2026-09-11T14:30:00+00:00",
        units="million_barrels", source="EIA",
        previous=-2.0, consensus=-1.0, actual=-5.0,
    )
    print(o["observation_id"])
    print("actual_vs_consensus:", o["actual_vs_consensus"])
