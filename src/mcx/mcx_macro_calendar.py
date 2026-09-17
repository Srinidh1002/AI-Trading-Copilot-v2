"""Event calendar — Section 4.8.
Registry + JSON loader. No hardcoded event times in strategy.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in __import__("sys").path:
    __import__("sys").path.insert(0, _SRC)

from mcx.mcx_macro_models import (
    SUPPORTED_EVENT_TYPES, make_event, _hash,
)


# Default event → importance + markets mapping. Section 4.12.
EVENT_METADATA = {
    "US_CPI":              {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "MEDIUM"}},
    "US_CORE_CPI":         {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "MEDIUM"}},
    "US_PPI":              {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "US_PCE":              {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "LOW"}},
    "US_CORE_PCE":         {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "US_FOMC_RATE":        {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "MEDIUM"}},
    "US_FOMC_STATEMENT":   {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "VERY_HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "MEDIUM"}},
    "US_NFP":              {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "MEDIUM"}},
    "US_UNEMPLOYMENT":     {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "US_AVG_HOURLY_EARNINGS": {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "US_GDP":              {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "HIGH", "NATGASMINI": "LOW"}},
    "US_RETAIL_SALES":     {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "MEDIUM", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "INDIA_CPI":           {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "MEDIUM", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "INDIA_RBI_MPC":       {"importance": "HIGH", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "HIGH", "CRUDEOILM": "MEDIUM", "NATGASMINI": "LOW"}},
    "INDIA_GDP":           {"importance": "MEDIUM", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "MEDIUM", "CRUDEOILM": "LOW", "NATGASMINI": "LOW"}},
    "INDIA_IIP":           {"importance": "LOW", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "LOW", "CRUDEOILM": "LOW", "NATGASMINI": "LOW"}},
    "INDIA_WPI":           {"importance": "LOW", "markets": ["GOLDM", "CRUDEOILM", "NATGASMINI"],
                            "relevance": {"GOLDM": "LOW", "CRUDEOILM": "LOW", "NATGASMINI": "LOW"}},
}


class MacroCalendar:
    def __init__(self, calendar_path=None):
        self.calendar_path = calendar_path or "data/macro_events/calendar/events_2026.json"
        self._events = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.calendar_path):
            return
        try:
            with open(self.calendar_path, encoding="utf-8") as f:
                data = json.load(f)
            for raw in data.get("events", []):
                ev = make_event(
                    event_type=raw["event_type"],
                    reference_period=raw["reference_period"],
                    release_date=raw["release_date"],
                    scheduled_local_time=raw["scheduled_local_time"],
                    source_tz=raw.get("source_tz", "America/New_York"),
                    source_agency=raw.get("source_agency", "UNKNOWN"),
                    source_identifier=raw.get("source_identifier"),
                    importance=raw.get("importance",
                        EVENT_METADATA.get(raw["event_type"], {}).get("importance", "MEDIUM")),
                    affected_markets=raw.get("affected_markets",
                        EVENT_METADATA.get(raw["event_type"], {}).get("markets", [])),
                    event_group_id=raw.get("event_group_id"),
                )
                self._events[ev["event_id"]] = ev
        except Exception:
            pass

    def register(self, event):
        self._events[event["event_id"]] = event

    def get(self, event_id):
        return self._events.get(event_id)

    def all_events(self):
        return sorted(self._events.values(), key=lambda e: e["scheduled_time_utc"])

    def upcoming(self, now_utc=None, hours=72):
        from datetime import datetime, timedelta, timezone
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        horizon = now_utc + timedelta(hours=hours)
        out = []
        for e in self.all_events():
            try:
                t = datetime.fromisoformat(e["scheduled_time_utc"])
            except Exception:
                continue
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if now_utc <= t <= horizon:
                out.append(e)
        return out

    def relevance_for(self, event_type, product):
        return EVENT_METADATA.get(event_type, {}).get("relevance", {}).get(product, "NONE")


if __name__ == "__main__":
    c = MacroCalendar()
    print(f"Loaded {len(c.all_events())} events")
    for e in c.all_events()[:5]:
        print(f"  {e['event_id']}  {e['scheduled_time_ist']}")
