"""Centralized Angel One Rate Limiter.
Token bucket + per-endpoint budget.
"""
import time
import threading


class AngelRateLimitCoordinator:
    def __init__(self):
        # Angel documented limits for getCandleData: 3/sec, 150/min, 5000/hr
        # Use conservative values
        self.limits = {
            "get_candle_data": {"per_second": 3, "per_minute": 120, "per_hour": 4500},
            "ltp_data":        {"per_second": 10, "per_minute": 300, "per_hour": 10000},
            "default":         {"per_second": 5, "per_minute": 200, "per_hour": 8000},
        }
        self._calls = {}  # endpoint -> [timestamps]
        self._lock = threading.Lock()
    
    def _prune(self, endpoint, now):
        if endpoint not in self._calls:
            self._calls[endpoint] = []
        # Keep last hour
        cutoff = now - 3600
        self._calls[endpoint] = [t for t in self._calls[endpoint] if t > cutoff]
    
    def _counts(self, endpoint, now):
        calls = self._calls.get(endpoint, [])
        return {
            "sec":   sum(1 for t in calls if t > now - 1),
            "min":   sum(1 for t in calls if t > now - 60),
            "hour":  sum(1 for t in calls if t > now - 3600),
        }
    
    def wait_if_needed(self, endpoint="default"):
        """Block until safe to make request."""
        limits = self.limits.get(endpoint, self.limits["default"])
        
        while True:
            with self._lock:
                now = time.time()
                self._prune(endpoint, now)
                counts = self._counts(endpoint, now)
                
                # Check limits
                if counts["sec"] >= limits["per_second"]:
                    sleep_for = 1.0 - (now - max(self._calls[endpoint]))
                elif counts["min"] >= limits["per_minute"]:
                    sleep_for = 2.0
                elif counts["hour"] >= limits["per_hour"]:
                    sleep_for = 5.0
                else:
                    # OK to proceed
                    self._calls[endpoint].append(now)
                    return True
            
            time.sleep(max(0.1, sleep_for))
    
    def stats(self):
        now = time.time()
        out = {}
        for ep in self._calls:
            out[ep] = self._counts(ep, now)
        return out


if __name__ == "__main__":
    rl = AngelRateLimitCoordinator()
    # Test: 6 rapid calls to a 3/sec endpoint
    start = time.time()
    for i in range(6):
        rl.wait_if_needed("get_candle_data")
        print(f"Call {i+1} at t={time.time()-start:.2f}s")
    print(f"Total: {time.time()-start:.2f}s for 6 calls (should be ~1s due to 3/sec limit)")
    print("Stats:", rl.stats())
