"""Canonical macro event models — Section 4.2, 4.3.
Deterministic record factories. No I/O, no network, no fabrication.
"""
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Documented event identifiers
SUPPORTED_EVENT_TYPES = (
    "US_CPI", "US_CORE_CPI", "US_PPI", "US_PCE", "US_CORE_PCE",
    "US_FOMC_RATE", "US_FOMC_STATEMENT",
    "US_NFP", "US_UNEMPLOYMENT", "US_AVG_HOURLY_EARNINGS",
    "US_GDP", "US_RETAIL_SALES",
    "INDIA_CPI", "INDIA_RBI_MPC", "INDIA_GDP", "INDIA_IIP", "INDIA_WPI",
)

STATUS_VALUES = ("SCHEDULED", "RELEASED", "REVISED", "CANCELLED", "DELAYED", "DATA_UNAVAILABLE")

# Per §4.12 — relevance categories only, not confidence points
RELEVANCE_VALUES = ("VERY_HIGH", "HIGH", "MEDIUM", "LOW", "NONE")

# Per §4.6
SURPRISE_CLASSES = (
    "LARGE_UPSIDE_SURPRISE", "MODERATE_UPSIDE_SURPRISE", "INLINE",
    "MODERATE_DOWNSIDE_SURPRISE", "LARGE_DOWNSIDE_SURPRISE",
    "UNCALIBRATED", "CONSENSUS_UNAVAILABLE",
)

# Per §4.15
REACTION_CLASSES = ("CONFIRMED", "PARTIALLY_CONFIRMED", "CONFLICTED", "INCONCLUSIVE", "DATA_UNAVAILABLE")

# Per §4.9
EVENT_STATES = ("NORMAL", "PRE_EVENT", "EVENT_LOCK",
                "POST_EVENT_DISCOVERY", "POST_EVENT_CONFIRMATION", "NORMALIZED")

# Documented shock thresholds for CPI YoY deviation (percentage points).
# These are EVENT CLASSIFICATION thresholds, NOT trading thresholds.
SURPRISE_SMALL_PP = 0.10
SURPRISE_MODERATE_PP = 0.30


def _hash(payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, sort_keys=True, default=str)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _to_ist_utc(src_dt):
    """Accept tz-aware datetime; return (utc_iso, ist_iso, src_iso)."""
    if src_dt.tzinfo is None:
        raise ValueError("scheduled time must be tz-aware")
    utc_iso = src_dt.astimezone(UTC).isoformat()
    ist_iso = src_dt.astimezone(IST).isoformat()
    src_iso = src_dt.isoformat()
    return utc_iso, ist_iso, src_iso


def make_metric(metric_id, units, period_type, previous=None,
                previous_revised=None, consensus=None, consensus_source=None,
                consensus_timestamp=None, actual=None, provenance=None):
    """Build a canonical MetricV1 dict."""
    avc = None
    if actual is not None and consensus is not None:
        try:
            avc = round(float(actual) - float(consensus), 6)
        except Exception:
            avc = None
    avp = None
    if actual is not None and previous is not None:
        try:
            avp = round(float(actual) - float(previous), 6)
        except Exception:
            avp = None
    return {
        "metric_id": metric_id,
        "units": units,
        "period_type": period_type,
        "previous": previous,
        "previous_revised": previous_revised,
        "consensus": consensus,
        "consensus_source": consensus_source,
        "consensus_timestamp": consensus_timestamp,
        "actual": actual,
        "actual_vs_consensus": avc,
        "actual_vs_previous": avp,
        "standardized_surprise": "UNCALIBRATED",
        "provenance": provenance or {},
    }


def make_event(event_type, reference_period, release_date,
               scheduled_local_time, source_tz, source_agency,
               source_identifier=None, importance="MEDIUM",
               affected_markets=None, event_group_id=None, metrics=None,
               status="SCHEDULED", raw_payload=None):
    """Build a canonical MacroEventV1 dict.
    scheduled_local_time: "HH:MM" local to source_tz
    release_date: "YYYY-MM-DD"
    source_tz: IANA tz name (e.g. America/New_York)
    """
    src_zone = ZoneInfo(source_tz)
    y, m, d = map(int, release_date.split("-"))
    hh, mm = map(int, scheduled_local_time.split(":"))
    src_dt = datetime(y, m, d, hh, mm, tzinfo=src_zone)
    utc_iso, ist_iso, src_iso = _to_ist_utc(src_dt)

    # Deterministic event_id
    event_id = f"{event_type}_{reference_period.replace('-', '_')}_{release_date.replace('-', '')}"

    ev = {
        "event_id": event_id,
        "event_type": event_type,
        "event_subtype": None,
        "event_group_id": event_group_id,
        "country": event_type.split("_")[0],
        "currency": {"US": "USD", "INDIA": "INR"}.get(event_type.split("_")[0], "UNKNOWN"),
        "reference_period": reference_period,
        "release_date": release_date,
        "scheduled_time_source_tz": source_tz,
        "scheduled_time_source_local": scheduled_local_time,
        "scheduled_time_src_iso": src_iso,
        "scheduled_time_utc": utc_iso,
        "scheduled_time_ist": ist_iso,
        "importance": importance,
        "affected_markets": affected_markets or [],
        "source_agency": source_agency,
        "source_identifier": source_identifier,
        "source_timestamp": None,
        "fetched_at": None,
        "raw_payload_hash": _hash(raw_payload) if raw_payload is not None else None,
        "status": status,
        "metrics": metrics or [],
    }
    return ev


def utc_now_iso():
    return datetime.now(UTC).isoformat()


def ist_now_iso():
    return datetime.now(IST).isoformat()


if __name__ == "__main__":
    e = make_event(
        event_type="US_CPI", reference_period="2026-08",
        release_date="2026-09-11", scheduled_local_time="08:30",
        source_tz="America/New_York", source_agency="BLS",
        importance="HIGH", affected_markets=["GOLDM", "CRUDEOILM", "NATGASMINI"])
    print(e["event_id"])
    print("IST:", e["scheduled_time_ist"])
    print("UTC:", e["scheduled_time_utc"])
