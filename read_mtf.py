import re
src = open("src/target_focused_bot.py", encoding="utf-8").read()
lines = src.splitlines()

# Find MTF fetch site
print("=== MTF fetch references ===")
for i, l in enumerate(lines, 1):
    if "get_candles" in l or "getCandleData" in l or "RATE_LIMIT" in l.upper() or "candle" in l.lower():
        print(f"  L{i}: {l.strip()[:140]}")
