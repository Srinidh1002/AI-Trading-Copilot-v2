src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
# search for a second MTF computation
import re
found = []
for i, l in enumerate(src):
    if "compute_mtf_indicators" in l or "get_multi_timeframe_technicals" in l:
        found.append(i)
for idx in found:
    print(f"=== context around L{idx+1} ===")
    for j in range(max(0, idx-4), min(len(src), idx+40)):
        print(f"{j+1:4d}: {src[j]}")
    print()
