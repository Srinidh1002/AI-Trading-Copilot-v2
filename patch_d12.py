"""D12 - tighten candle rate limiter + shorten failure cooldown.

Observed in N4 smoke: 4 candle calls in cycle 1 hit provider rate limit.
Then _mark_failed set a 120s cooldown that kept MTF broken for 4 cycles.

Fix:
  1. get_candle_data per_second: 3 -> 1 (per observed provider behavior)
  2. failure cooldown: 120s -> 30s
  3. add explicit inter-timeframe delay in MTF loop (stagger fetch)
"""
import os

# --- rate_limiter.py ---
p1 = "src/rate_limiter.py"
with open(p1, encoding="utf-8") as f:
    s1 = f.read()
if "D12_tighter" in s1:
    print("D12 rate_limiter already applied")
else:
    old = '"get_candle_data": {"per_second": 3, "per_minute": 120, "per_hour": 4500},'
    new = '"get_candle_data": {"per_second": 1, "per_minute": 60, "per_hour": 3600},  # D12_tighter'
    if old not in s1:
        raise SystemExit("D12: rate_limiter anchor not found")
    s1 = s1.replace(old, new, 1)
    with open(p1, "w", encoding="utf-8") as f:
        f.write(s1)
    print("D12: rate_limiter get_candle_data now 1/sec 60/min 3600/hr")

# --- market_intelligence.py ---
p2 = "src/market_intelligence.py"
with open(p2, encoding="utf-8") as f:
    s2 = f.read()
if "D12_cooldown_30" in s2:
    print("D12 market_intelligence already applied")
else:
    old = 'return (time.time() - self._cache_time[key]) < 120'
    new = 'return (time.time() - self._cache_time[key]) < 30  # D12_cooldown_30'
    if old not in s2:
        raise SystemExit("D12: market_intelligence anchor not found")
    s2 = s2.replace(old, new, 1)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(s2)
    print("D12: failure cooldown 120s -> 30s")

# --- target_focused_bot.py --- add inter-tf stagger ---
p3 = "src/target_focused_bot.py"
with open(p3, encoding="utf-8") as f:
    s3 = f.read()
if "D12_stagger" in s3:
    print("D12 stagger already applied")
else:
    old = '''                tf_map = {"1h": "ONE_HOUR", "15m": "FIFTEEN_MINUTE", "5m": "FIVE_MINUTE"}
                mtf_full = {}
                for tf_name, tf_interval in tf_map.items():
                    df = self.market_intel.get_candles(tf_interval, days_back=10 if tf_name == "1h" else 5)
                    if df is not None and len(df) >= 26:
                        ind = compute_mtf_indicators(df)
                        mtf_full[tf_name] = ind'''
    new = '''                tf_map = {"1h": "ONE_HOUR", "15m": "FIFTEEN_MINUTE", "5m": "FIVE_MINUTE"}
                mtf_full = {}
                for tf_name, tf_interval in tf_map.items():
                    df = self.market_intel.get_candles(tf_interval, days_back=10 if tf_name == "1h" else 5)
                    if df is not None and len(df) >= 26:
                        ind = compute_mtf_indicators(df)
                        mtf_full[tf_name] = ind
                    time.sleep(0.4)  # D12_stagger - space out candle requests'''
    if old not in s3:
        raise SystemExit("D12: bot MTF loop anchor not found")
    s3 = s3.replace(old, new, 1)
    with open(p3, "w", encoding="utf-8") as f:
        f.write(s3)
    print("D12: MTF loop now staggers by 0.4s between timeframes")
