import re
src = open("src/target_focused_bot.py", encoding="utf-8").read()
lines = src.splitlines()

print("=== F09 candle-cache hits in bot ===")
for i, l in enumerate(lines, 1):
    if re.search(r"candle_cache|CandleBuilder|_candles", l, re.I):
        print(f"  L{i}: {l.strip()[:120]}")

print()
print("=== F10 failure-TTL hits across src/ ===")
import os
for fn in sorted(os.listdir("src")):
    if not fn.endswith(".py"): continue
    p = f"src/{fn}"
    with open(p, encoding="utf-8") as f:
        for i, l in enumerate(f, 1):
            if re.search(r"failure_ttl|FAILURE_TTL|_ttl\b|TTL\b", l):
                print(f"  {fn}:{i}: {l.strip()[:120]}")
