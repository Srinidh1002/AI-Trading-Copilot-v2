"""Quote Freshness - Detects stale vs fresh quotes.
Distinguishes PRICE_UNCHANGED from NO_NEW_QUOTE.
"""
import time
from datetime import datetime
from typing import Optional


class QuoteFreshnessTracker:
    def __init__(self, freshness_budget_seconds=90):  # REST cadence: WS is broken, 50s polls + buffer
        self.budget = freshness_budget_seconds
        self._last_seen = {}  # symbol -> {ltp, provider_ts, local_ts, seq}
    
    def update(self, symbol, ltp, provider_timestamp=None, sequence_id=None):
        """Record new quote. Returns freshness status."""
        now = time.time()
        prev = self._last_seen.get(symbol)
        
        status = "FRESH"
        
        if prev is not None:
            prev_ltp = prev["ltp"]
            prev_ts = prev["provider_ts"]
            
            # Same price?
            same_price = abs(ltp - prev_ltp) < 0.001
            
            # Same provider timestamp?
            same_ts = (provider_timestamp is not None and 
                       provider_timestamp == prev_ts)
            
            if same_ts and same_price:
                status = "POSSIBLY_STALE"
            elif same_price and not same_ts:
                status = "FRESH_UNCHANGED_PRICE"
            elif provider_timestamp is not None and prev_ts is not None:
                if provider_timestamp < prev_ts:
                    status = "OUT_OF_ORDER"
        
        self._last_seen[symbol] = {
            "ltp": ltp,
            "provider_ts": provider_timestamp,
            "local_ts": now,
            "seq": sequence_id
        }
        
        age = 0
        if prev is not None:
            age = now - prev["local_ts"]

        # RULE 8: age > budget means STALE regardless of tick equality
        if age > self.budget and status in ("FRESH", "FRESH_UNCHANGED_PRICE"):
            status = "STALE"

        return {
            "status": status,
            "age_seconds": age,
            "budget_seconds": self.budget,
            "fresh": status in ("FRESH", "FRESH_UNCHANGED_PRICE") and age < self.budget,
            "ltp": ltp
        }
    
    def get_age(self, symbol) -> Optional[float]:
        if symbol not in self._last_seen:
            return None
        return time.time() - self._last_seen[symbol]["local_ts"]
    
    def is_fresh(self, symbol) -> bool:
        age = self.get_age(symbol)
        if age is None:
            return False
        return age < self.budget


if __name__ == "__main__":
    tracker = QuoteFreshnessTracker(freshness_budget_seconds=10)
    
    # Test 1: first quote
    r = tracker.update("NIFTY", 23450.0, provider_timestamp="2026-09-10T15:00:00")
    print(f"First: {r['status']}")
    
    # Test 2: same price, new timestamp
    time.sleep(0.1)
    r = tracker.update("NIFTY", 23450.0, provider_timestamp="2026-09-10T15:00:01")
    print(f"Same price new ts: {r['status']}")
    
    # Test 3: same price, same timestamp
    time.sleep(0.1)
    r = tracker.update("NIFTY", 23450.0, provider_timestamp="2026-09-10T15:00:01")
    print(f"Same price same ts: {r['status']}")
    
    # Test 4: new price
    time.sleep(0.1)
    r = tracker.update("NIFTY", 23451.0, provider_timestamp="2026-09-10T15:00:02")
    print(f"New price: {r['status']}")
    
    # Test 5: out of order
    time.sleep(0.1)
    r = tracker.update("NIFTY", 23449.0, provider_timestamp="2026-09-10T14:59:00")
    print(f"Out of order: {r['status']}")
