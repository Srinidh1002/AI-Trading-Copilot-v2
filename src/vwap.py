"""INDEX_SESSION_TWAP Calculator

NOTE: This is NOT a true volume-weighted VWAP because indices have no
directly traded volume. This class computes a time-weighted average
price (TWAP) from index ticks. For true VWAP, use NIFTY/SENSEX futures.

Naming: VWAPTracker retained for backward compat, but semantics are TWAP.
"""


class VWAPTracker:
    def __init__(self):
        self._cum_pv = 0.0   # cumulative price*volume
        self._cum_vol = 0.0  # cumulative volume
        self._sum_price = 0.0
        self._count = 0
        self._session_date = None
        self.high = None
        self.low = None
    
    def on_tick(self, price, volume=1, ts=None):
        """Accumulate tick. Volume defaults to 1 (tick count VWAP)."""
        from datetime import datetime
        if ts is None:
            ts = datetime.now()
        
        # Reset on new day
        today = ts.date() if hasattr(ts, "date") else None
        if today and self._session_date != today:
            self.reset()
            self._session_date = today
        
        if price <= 0:
            return
        
        self._cum_pv += price * volume
        self._cum_vol += volume
        self._sum_price += price
        self._count += 1
        
        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price
    
    def on_candle(self, open_p, high, low, close, volume):
        """Accumulate from REST candle."""
        if volume <= 0:
            volume = 1
        typical = (high + low + close) / 3
        self._cum_pv += typical * volume
        self._cum_vol += volume
        self._sum_price += close
        self._count += 1
    
    def reset(self):
        self._cum_pv = 0.0
        self._cum_vol = 0.0
        self._sum_price = 0.0
        self._count = 0
        self.high = None
        self.low = None
    
    @property
    def vwap(self):
        if self._cum_vol > 0:
            return self._cum_pv / self._cum_vol
        if self._count > 0:
            return self._sum_price / self._count
        return None
    
    def position(self, price):
        """Where is price relative to VWAP?"""
        v = self.vwap
        if v is None or price <= 0:
            return "UNKNOWN"
        diff_pct = ((price - v) / v) * 100
        if diff_pct > 0.1:
            return "ABOVE"
        elif diff_pct < -0.1:
            return "BELOW"
        return "AT"
    
    def describe(self, price=None):
        v = self.vwap
        return {
            "vwap": v,
            "high": self.high,
            "low": self.low,
            "ticks": self._count,
            "position": self.position(price) if price else "UNKNOWN",
        }


if __name__ == "__main__":
    v = VWAPTracker()
    
    # Simulate session
    from datetime import datetime
    base = datetime(2026, 9, 10, 9, 15, 0)
    import random
    random.seed(42)
    for i in range(300):
        price = 23400 + random.uniform(-20, 20)
        v.on_tick(price, volume=random.randint(50, 500), ts=base)
    
    print("VWAP:", round(v.vwap, 2))
    print("High:", round(v.high, 2))
    print("Low:", round(v.low, 2))
    print("Ticks:", v._count)
    print("Current price position (23410):", v.position(23410))
