"""Opening Range - First 5/15/30 min ranges + breakout status."""
from datetime import datetime, time


class OpeningRangeTracker:
    def __init__(self):
        self.ranges = {
            "5m":  {"high": None, "low": None, "start": None, "end": None, "locked": False},
            "15m": {"high": None, "low": None, "start": None, "end": None, "locked": False},
            "30m": {"high": None, "low": None, "start": None, "end": None, "locked": False},
        }
        self.session_date = None
        self.session_open = None
    
    def _reset(self, session_date):
        self.session_date = session_date
        for k in self.ranges:
            self.ranges[k] = {"high": None, "low": None, "start": None, "end": None, "locked": False}
    
    def _is_within(self, ts, minutes):
        """Check if ts is within first N minutes of session."""
        if not self.session_open:
            return False
        delta = (ts - self.session_open).total_seconds() / 60.0
        return 0 <= delta < minutes
    
    def _has_passed(self, ts, minutes):
        if not self.session_open:
            return False
        delta = (ts - self.session_open).total_seconds() / 60.0
        return delta >= minutes
    
    def on_tick(self, price, ts=None):
        """Update ranges. Also lock them once their window passes."""
        if ts is None:
            ts = datetime.now()
        
        # Reset on new day
        today = ts.date() if hasattr(ts, "date") else None
        if today and self.session_date != today:
            self._reset(today)
            self.session_open = None
        
        # Detect session open (first tick after 9:15)
        if self.session_open is None:
            if ts.time() >= time(9, 15):
                self.session_open = ts
                for k in self.ranges:
                    self.ranges[k]["start"] = ts
        
        if price <= 0 or not self.session_open:
            return
        
        for interval, minutes in [("5m", 5), ("15m", 15), ("30m", 30)]:
            r = self.ranges[interval]
            if r["locked"]:
                continue
            if self._is_within(ts, minutes):
                if r["high"] is None:
                    r["high"] = price
                    r["low"] = price
                else:
                    r["high"] = max(r["high"], price)
                    r["low"] = min(r["low"], price)
            elif self._has_passed(ts, minutes):
                r["locked"] = True
                r["end"] = ts
    
    def breakout_status(self, price, interval="15m"):
        """Is price breaking out of this range?"""
        r = self.ranges.get(interval)
        if not r or r["high"] is None:
            return "UNKNOWN"
        if price > r["high"]:
            return "BREAKOUT_UP"
        elif price < r["low"]:
            return "BREAKOUT_DOWN"
        return "INSIDE"
    
    def describe(self, price=None):
        out = {}
        for k, r in self.ranges.items():
            width = None
            if r["high"] and r["low"]:
                width = r["high"] - r["low"]
            status = self.breakout_status(price, k) if price else "UNKNOWN"
            out[k] = {
                "high": r["high"],
                "low": r["low"],
                "width": width,
                "locked": r["locked"],
                "status": status,
            }
        return out


if __name__ == "__main__":
    ort = OpeningRangeTracker()
    base = datetime(2026, 9, 10, 9, 15, 0)
    import random
    random.seed(42)
    
    # Simulate 45 minutes of ticks
    for i in range(45 * 60):  # 45 min at 1 tick/sec
        from datetime import timedelta
        ts = base + timedelta(seconds=i)
        price = 23400 + random.uniform(-15, 15)
        ort.on_tick(price, ts=ts)
    
    print("Opening ranges:")
    for k, v in ort.describe(price=23410).items():
        print(f"  {k}: H={v['high']:.2f} L={v['low']:.2f} W={v['width']:.2f} locked={v['locked']} status={v['status']}")
