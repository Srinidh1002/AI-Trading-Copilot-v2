"""Macro event engine — Sections 4.9, 4.29, 4.30, 4.33.
Shadow-only. NEVER modifies trade decisions.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_macro_calendar import MacroCalendar, EVENT_METADATA
from mcx.mcx_macro_models import EVENT_STATES
from mcx.mcx_macro_surprise import enrich_event, classify_surprise


# Event observation windows (Section 4.9). DOCUMENTED values.
# These are observation windows, NOT entry-block thresholds.
PRE_EVENT_MINUTES = 15
RELEASE_LOCK_MINUTES = 2
DISCOVERY_MINUTES = 5
CONFIRMATION_MINUTES = 20


def classify_state(now_utc, event):
    """Determine shadow state for a single event."""
    try:
        rel = datetime.fromisoformat(event["scheduled_time_utc"])
    except Exception:
        return "NORMAL", "unparseable_schedule"
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    delta_seconds = (now_utc - rel).total_seconds()
    if delta_seconds < -PRE_EVENT_MINUTES * 60:
        return "NORMAL", f"T-{int(-delta_seconds/60)}m"
    if -PRE_EVENT_MINUTES * 60 <= delta_seconds < 0:
        return "PRE_EVENT", f"T{int(delta_seconds/60)}m"
    if 0 <= delta_seconds < RELEASE_LOCK_MINUTES * 60:
        return "EVENT_LOCK", f"T+{int(delta_seconds)}s"
    if RELEASE_LOCK_MINUTES * 60 <= delta_seconds < (RELEASE_LOCK_MINUTES + DISCOVERY_MINUTES) * 60:
        return "POST_EVENT_DISCOVERY", f"T+{int(delta_seconds/60)}m"
    if (RELEASE_LOCK_MINUTES + DISCOVERY_MINUTES) * 60 <= delta_seconds < \
       (RELEASE_LOCK_MINUTES + DISCOVERY_MINUTES + CONFIRMATION_MINUTES) * 60:
        return "POST_EVENT_CONFIRMATION", f"T+{int(delta_seconds/60)}m"
    return "NORMALIZED", f"T+{int(delta_seconds/60)}m"


class MacroEngine:
    def __init__(self, calendar=None):
        self.calendar = calendar or MacroCalendar()
        self.shadow_mode = True

    def aggregate_state(self, now_utc):
        """Return dict of per-event states + highest active."""
        events = self.calendar.all_events()
        active = []
        for e in events:
            state, reason = classify_state(now_utc, e)
            if state in ("PRE_EVENT", "EVENT_LOCK", "POST_EVENT_DISCOVERY", "POST_EVENT_CONFIRMATION"):
                active.append({"event": e, "state": state, "reason": reason})

        # Aggregate highest risk
        risk_order = {"EVENT_LOCK": 4, "PRE_EVENT": 3, "POST_EVENT_DISCOVERY": 2,
                      "POST_EVENT_CONFIRMATION": 1}
        agg = "NORMAL"
        if active:
            agg = max(active, key=lambda a: risk_order.get(a["state"], 0))["state"]
        return {"aggregate_state": agg, "active": active}

    def nearest_event(self, now_utc):
        """Return nearest upcoming event within 72h. now_utc may be naive or aware."""
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        upcoming = self.calendar.upcoming(now_utc, hours=72)
        if not upcoming:
            return None
        return upcoming[0]

    def shadow_report_for(self, product, now_utc):
        """Shadow report — never passed to compose_decision."""
        from mcx.mcx_macro_calendar import EVENT_METADATA as META
        near = self.nearest_event(now_utc)
        agg = self.aggregate_state(now_utc)
        if not near:
            return {"product": product, "state": agg["aggregate_state"],
                    "next_event": None, "shadow_only": True, "trade_influence": False}
        rel = self.calendar.relevance_for(near["event_type"], product)
        return {
            "product": product,
            "state": agg["aggregate_state"],
            "next_event": near["event_id"],
            "next_event_type": near["event_type"],
            "next_event_ist": near["scheduled_time_ist"],
            "relevance": rel,
            "importance": META.get(near["event_type"], {}).get("importance", "MEDIUM"),
            "shadow_only": True,
            "trade_influence": False,
        }


if __name__ == "__main__":
    from datetime import datetime, timezone
    e = MacroEngine()
    now = datetime(2026, 9, 11, 12, 45, tzinfo=timezone.utc)  # 18:15 IST
    for p in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        print(e.shadow_report_for(p, now))
