import re
src = open("src/target_focused_bot.py", encoding="utf-8").read()
lines = src.splitlines()
print("=== technicals pillar references ===")
for i, l in enumerate(lines, 1):
    if "TECHNICAL_MTF_INSUFFICIENT_DATA" in l or "INSUFFICIENT_DATA" in l or "Technicals (MTF)" in l or "compute_mtf_indicators" in l:
        print(f"  L{i}: {l.strip()[:150]}")
