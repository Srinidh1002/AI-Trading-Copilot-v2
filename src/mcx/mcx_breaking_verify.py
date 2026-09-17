"""Verification + source independence — Section 6.5, 6.6, 6.48, 6.49, 6.50."""
import hashlib

import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_breaking_models import VERIFICATION_STATES


def classify_independence(sources):
    """Section 6.6 — sources with same originating wire are NOT independent."""
    originators = set()
    publishers = set()
    for s in sources:
        originators.add(s.get("originating_source") or s.get("source_name"))
        publishers.add(s.get("source_name"))
    return {
        "unique_originators": len(originators),
        "unique_publishers": len(publishers),
        "is_independent": len(originators) >= 2,
    }


def compute_verification(sources):
    """Deterministic verification state from a list of source reports.
    sources = list of dicts: {source_name, source_tier, originating_source, confirms(bool)}
    """
    if not sources:
        return "UNRESOLVED", "no_sources"

    # Any official confirmation?
    for s in sources:
        if s.get("source_tier") == "TIER_1_OFFICIAL" and s.get("confirms", True):
            return "OFFICIALLY_CONFIRMED", "official_source_confirms"

    # Disputed: sources conflict
    confirms = [s for s in sources if s.get("confirms", True)]
    denies = [s for s in sources if not s.get("confirms", True)]
    if confirms and denies:
        return "DISPUTED", "sources_disagree"

    # Retraction / false
    for s in sources:
        if s.get("retracted"):
            return "RETRACTED", "source_retracted"

    # Corroboration by independent originators (Section 6.6)
    ind = classify_independence(sources)
    if ind["is_independent"] and ind["unique_originators"] >= 2:
        return "MULTI_SOURCE_CORROBORATED", f"independent={ind['unique_originators']}"

    if len(sources) >= 1:
        return "SINGLE_SOURCE", "single_source_only"

    return "UNRESOLVED", "insufficient_evidence"


def verify_event(event, source_reports):
    """Return updated event with verification_status. Pure — no I/O."""
    out = dict(event)
    status, reason = compute_verification(source_reports)
    if status not in VERIFICATION_STATES:
        status = "UNRESOLVED"
    out["verification_status"] = status
    out["_verification_reason"] = reason
    return out


if __name__ == "__main__":
    # Same wire copied by 3 sites → NOT independent
    s1 = [{"source_name": "SiteA", "source_tier": "TIER_4_SECONDARY", "originating_source": "Reuters"},
          {"source_name": "SiteB", "source_tier": "TIER_4_SECONDARY", "originating_source": "Reuters"},
          {"source_name": "SiteC", "source_tier": "TIER_4_SECONDARY", "originating_source": "Reuters"}]
    print("3 copies of same wire:", compute_verification(s1))
    s2 = [{"source_name": "Reuters", "source_tier": "TIER_2_MAJOR_WIRE", "originating_source": "Reuters"},
          {"source_name": "AP", "source_tier": "TIER_2_MAJOR_WIRE", "originating_source": "AP"}]
    print("2 independent:", compute_verification(s2))
    s3 = [{"source_name": "OPEC", "source_tier": "TIER_1_OFFICIAL", "confirms": True}]
    print("official:", compute_verification(s3))
