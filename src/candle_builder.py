"""Candle Builder - Constructs OHLC candles from live ticks.
Supports multiple intervals simultaneously.
"""
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque


INTERVALS = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
}


class CandleBuilder:
    def __init__(self, max_history=500):
        self.max_history = max_history
        self._lock = threading.Lock()
        # token -> interval -> deque of completed candles
        self.completed = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_history))
        )
        # token -> interval -> current in-progress candle
        self.current = defaultdict(dict)
    
    def _bucket_start(self, ts, minutes):
        """Floor timestamp to interval boundary."""
        if minutes == 60:
            return ts.replace(minute=0, second=0, microsecond=0)
        minute = (ts.minute // minutes) * minutes
        return ts.replace(minute=minute, second=0, microsecond=0)
    
    def on_tick(self, token, price, ts=None):
        """Ingest one tick. Rolls over candles at boundaries."""
        if ts is None:
            ts = datetime.now()
        token = str(token)
        
        if price <= 0:
            return
        
        with self._lock:
            for interval, minutes in INTERVALS.items():
                bucket = self._bucket_start(ts, minutes)
                curr = self.current[token].get(interval)
                
                if curr is None or curr["bucket"] != bucket:
                    # Close previous candle
                    if curr is not None:
                        self.completed[token][interval].append(dict(curr))
                    
                    # Start new candle
                    self.current[token][interval] = {
                        "bucket": bucket,
                        "timestamp": bucket,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                        "ticks": 1,
                    }
                else:
                    curr["high"] = max(curr["high"], price)
                    curr["low"] = min(curr["low"], price)
                    curr["close"] = price
                    curr["ticks"] += 1
    
    def seed_from_rest(self, token, interval, rest_candles):
        """Seed completed candles from REST history.
        rest_candles: list of [timestamp, open, high, low, close, volume]
        """
        token = str(token)
        with self._lock:
            for row in rest_candles:
                try:
                    ts = datetime.fromisoformat(str(row[0]).replace("Z", ""))
                    candle = {
                        "bucket": ts,
                        "timestamp": ts,
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]) if len(row) > 5 else 0,
                        "source": "REST_SEED",
                    }
                    self.completed[token][interval].append(candle)
                except Exception:
                    continue
    
    def get_recent(self, token, interval, count=200):
        """Return last `count` candles (completed + current) as list of dicts."""
        token = str(token)
        with self._lock:
            completed = list(self.completed[token].get(interval, []))
            curr = self.current[token].get(interval)
            out = completed[:]
            if curr:
                out.append(dict(curr))
            return out[-count:]
    
    def get_completed(self, token, interval, count=200):
        token = str(token)
        with self._lock:
            return list(self.completed[token].get(interval, []))[-count:]
    
    def has_enough(self, token, interval, min_count):
        return len(self.get_recent(token, interval)) >= min_count


if __name__ == "__main__":
    cb = CandleBuilder()
    
    # Simulate ticks over 5 minutes
    base = datetime(2026, 9, 10, 9, 15, 0)
    for i in range(300):  # 300 seconds
        ts = base + timedelta(seconds=i)
        price = 23400 + (i % 20) * 0.5
        cb.on_tick("99926000", price, ts=ts)
    
    print("1m candles:", len(cb.get_completed("99926000", "1m")))
    print("5m candles:", len(cb.get_completed("99926000", "5m")))
    print("15m candles:", len(cb.get_completed("99926000", "15m")))
    print()
    print("Last 1m candle:")
    last = cb.get_completed("99926000", "1m")[-1]
    print(f"  ts={last['timestamp']} O={last['open']:.2f} H={last['high']:.2f} L={last['low']:.2f} C={last['close']:.2f} ticks={last['ticks']}")
    print()
    print("Current in-progress 1m:")
    curr = cb.get_recent("99926000", "1m", count=1)[0]
    print(f"  O={curr['open']:.2f} H={curr['high']:.2f} L={curr['low']:.2f} C={curr['close']:.2f}")
