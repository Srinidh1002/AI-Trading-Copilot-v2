"""D13 - do not cache INSUFFICIENT_DATA technicals consensus.

Root cause (N4 smoke): get_multi_timeframe_technicals() caches the entire
result dict for 600s. When cycle 1 hit RATE_LIMITED on 2 of 3 timeframes,
consensus = INSUFFICIENT_DATA got cached. Cycles 2-8 all hit the cache
and never re-evaluated, even after candles became available.

Fix: cache ONLY successful consensus states (BULLISH/BEARISH/WEAK_*/MIXED).
Never cache INSUFFICIENT_DATA or UNKNOWN. Short cooldown via existing
per-interval failure mechanism already prevents rate-limit thrashing.
"""
path = "src/market_intelligence.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D13_no_cache_incomplete" in src:
    print("D13 already applied")
    raise SystemExit(0)

old = '''        self._store("technicals", result)
        return result'''
new = '''        # D13_no_cache_incomplete - never cache transient incomplete results
        _cons = result.get("consensus")
        if _cons not in ("INSUFFICIENT_DATA", "UNKNOWN", None):
            self._store("technicals", result)
        return result'''

if old not in src:
    raise SystemExit("D13 anchor not found")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D13: technicals consensus no longer caches incomplete results")
