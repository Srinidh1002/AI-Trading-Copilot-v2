"""Economic Calendar - Time-aware high-impact event tracker.
Uses hardcoded recurring events + configurable events list.
"""
from datetime import datetime, time, timedelta
from typing import List, Dict


class EconomicCalendarEngine:
    # Hardcoded recurring monthly events (day of month)
    # Expand as needed
    RECURRING = {
        # RBI policy dates (roughly bi-monthly) - would need manual update
        # CPI/WPI releases (12th-14th of month typically)
        "IN_CPI": {"typical_day": 12, "time": (17, 30), "importance": "HIGH"},
        "IN_WPI": {"typical_day": 14, "time": (12, 0), "importance": "MEDIUM"},
    }
    
    def __init__(self):
        # Can be populated externally with actual calendar
        self.events = []
    
    def add_event(self, name: str, when: datetime, importance: str = "HIGH",
                  country: str = "IN", notes: str = ""):
        """Register an event."""
        self.events.append({
            "name": name,
            "when": when,
            "importance": importance,
            "country": country,
            "notes": notes,
        })
    
    def add_recurring(self, name: str, day_of_month: int, event_time: tuple,
                      importance: str = "HIGH", country: str = "IN"):
        """Add recurring monthly event for upcoming month."""
        now = datetime.now()
        try:
            evt_dt = now.replace(day=day_of_month, hour=event_time[0],
                                 minute=event_time[1], second=0, microsecond=0)
            if evt_dt < now:
                # Move to next month
                if now.month == 12:
                    evt_dt = evt_dt.replace(year=now.year + 1, month=1)
                else:
                    evt_dt = evt_dt.replace(month=now.month + 1)
            self.add_event(name, evt_dt, importance, country)
        except ValueError:
            pass
    
    def load_recurring(self):
        """Load current month's recurring events."""
        for name, cfg in self.RECURRING.items():
            self.add_recurring(name, cfg["typical_day"], cfg["time"], cfg["importance"])
    
    def minutes_to_next_high_impact(self, threshold_minutes: int = 10) -> Dict:
        """Check if any high-impact event is within threshold."""
        now = datetime.now()
        upcoming = []
        for e in self.events:
            if e["importance"] != "HIGH":
                continue
            delta_min = (e["when"] - now).total_seconds() / 60.0
            if 0 <= delta_min <= threshold_minutes:
                upcoming.append({
                    "name": e["name"],
                    "in_minutes": round(delta_min, 1),
                    "country": e["country"],
                })
        
        if upcoming:
            return {
                "status": "HIGH_IMPACT_EVENT_WITHIN_THRESHOLD",
                "threshold_minutes": threshold_minutes,
                "events": upcoming,
                "block_entries": True,
            }
        return {
            "status": "CLEAR",
            "threshold_minutes": threshold_minutes,
            "events": [],
            "block_entries": False,
        }
    
    def upcoming_today(self) -> List[Dict]:
        """All events remaining today."""
        now = datetime.now()
        today_end = now.replace(hour=23, minute=59, second=59)
        return [
            {"name": e["name"], "at": e["when"].strftime("%H:%M"),
             "importance": e["importance"], "country": e["country"]}
            for e in sorted(self.events, key=lambda x: x["when"])
            if now <= e["when"] <= today_end
        ]


if __name__ == "__main__":
    eng = EconomicCalendarEngine()
    eng.load_recurring()
    
    # Add a test event 5 minutes from now
    from datetime import timedelta
    eng.add_event("TEST_EVENT", datetime.now() + timedelta(minutes=5), "HIGH")
    eng.add_event("FED_MEETING", datetime.now() + timedelta(hours=4), "HIGH")
    
    print("Upcoming today:")
    for e in eng.upcoming_today():
        print(f"  {e}")
    
    print()
    print("High-impact check (10 min):", eng.minutes_to_next_high_impact(10))
    print("High-impact check (2 min):", eng.minutes_to_next_high_impact(2))
