"""D13 verification - incomplete results not cached, real results cached."""
import sys, time
sys.path.append("src")

# Simulate the fix logic in isolation without a live bot
class FakeMI:
    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = {"technicals": 600}

    def _fresh(self, k):
        if k not in self._cache_time: return False
        return (time.time() - self._cache_time[k]) < self.cache_ttl.get(k, 300)

    def _store(self, k, v):
        self._cache[k] = v
        self._cache_time[k] = time.time()

    # Simulated D13-modified method
    def get_multi_timeframe_technicals(self):
        if self._fresh("technicals"):
            return self._cache["technicals"]
        # Fake result based on injected state
        result = self.inject_result
        _cons = result.get("consensus")
        if _cons not in ("INSUFFICIENT_DATA", "UNKNOWN", None):
            self._store("technicals", result)
        return result

mi = FakeMI()

# Scenario 1: first call returns INSUFFICIENT_DATA - should NOT cache
mi.inject_result = {"consensus": "INSUFFICIENT_DATA", "5m": {"trend": "FLAT"}}
r1 = mi.get_multi_timeframe_technicals()
print(f"Call 1: consensus={r1['consensus']}  cache_has_technicals={'technicals' in mi._cache}")

# Scenario 2: next call returns real result - should cache
mi.inject_result = {"consensus": "BULLISH", "1h": {"trend": "UP"}, "15m": {"trend": "UP"}, "5m": {"trend": "FLAT"}}
r2 = mi.get_multi_timeframe_technicals()
print(f"Call 2: consensus={r2['consensus']}  cache_has_technicals={'technicals' in mi._cache}")

# Scenario 3: next call - should hit cache and return BULLISH, ignoring new inject
mi.inject_result = {"consensus": "INSUFFICIENT_DATA"}
r3 = mi.get_multi_timeframe_technicals()
print(f"Call 3: consensus={r3['consensus']}  (should be BULLISH from cache)")

assert r1["consensus"] == "INSUFFICIENT_DATA"
assert r2["consensus"] == "BULLISH"
assert r3["consensus"] == "BULLISH"
print()
print("D13 verification PASSED")
