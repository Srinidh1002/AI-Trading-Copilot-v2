"""Dedup + clustering — Section 6.7, 6.8, 6.9, 6.47."""
import hashlib
import os, sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_breaking_models import normalize_headline, _hash


def event_fingerprint(event):
    """Deterministic fingerprint for dedup.
    Combines: event_type + sorted countries + sorted infra + normalized headline.
    """
    parts = [
        event.get("event_type", ""),
        ",".join(sorted(event.get("countries") or [])),
        ",".join(sorted(event.get("infrastructure") or [])),
        normalize_headline(event.get("headline", ""))[:80],
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def classify_against_existing(new_event, existing_events, time_window_seconds=3600):
    """Return (class, related_event_id).
    Sections 6.7 + 6.9.
    """
    if not existing_events:
        return "NEW_EVENT", None

    try:
        new_pub = datetime.fromisoformat(new_event.get("source_published_at") or "")
    except Exception:
        new_pub = datetime.now(timezone.utc)
    if new_pub.tzinfo is None:
        new_pub = new_pub.replace(tzinfo=timezone.utc)

    new_fp = event_fingerprint(new_event)

    best = None
    for ex in existing_events:
        ex_fp = event_fingerprint(ex)
        # Same fingerprint = duplicate
        if new_fp == ex_fp:
            return "DUPLICATE", ex.get("event_id")
        # Same event_type + same countries within window = update / correction candidate
        same_type = ex.get("event_type") == new_event.get("event_type")
        same_countries = set(ex.get("countries") or []) == set(new_event.get("countries") or [])
        if same_type and same_countries:
            try:
                ex_pub = datetime.fromisoformat(ex.get("source_published_at") or "")
                if ex_pub.tzinfo is None:
                    ex_pub = ex_pub.replace(tzinfo=timezone.utc)
                gap = abs((new_pub - ex_pub).total_seconds())
            except Exception:
                gap = 0
            if gap <= time_window_seconds:
                if new_event.get("retraction_of"):
                    return "RETRACTION", ex.get("event_id")
                if new_event.get("correction_of"):
                    return "CORRECTION", ex.get("event_id")
                return "UPDATE", ex.get("event_id")
        # Same cluster = related
        if (ex.get("event_cluster_id") and
            ex.get("event_cluster_id") == new_event.get("event_cluster_id")):
            best = ex.get("event_id")
    if best:
        return "RELATED_SEPARATE_EVENT", best
    return "NEW_EVENT", None


if __name__ == "__main__":
    e1 = {"event_type": "PIPELINE_OUTAGE", "countries": ["IRQ"], "headline": "Pipeline shut",
          "source_published_at": "2026-09-12T10:00:00+00:00", "event_id": "E1"}
    e2 = {"event_type": "PIPELINE_OUTAGE", "countries": ["IRQ"], "headline": "Pipeline shut",
          "source_published_at": "2026-09-12T10:00:00+00:00", "event_id": "E2"}
    print("duplicate:", classify_against_existing(e2, [e1]))
    e3 = {"event_type": "PIPELINE_OUTAGE", "countries": ["IRQ"], "headline": "Pipeline operator confirms shut",
          "source_published_at": "2026-09-12T10:05:00+00:00", "event_id": "E3"}
    print("update:", classify_against_existing(e3, [e1]))
