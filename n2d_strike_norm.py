import sys
sys.path.append("src")
src = open("src/target_focused_bot.py", encoding="utf-8").read()
lines = src.splitlines()
import re
print("=== strike normalization references in bot ===")
for i, l in enumerate(lines, 1):
    if re.search(r"strike.*100|100.*strike|/ 100|strike\s*=\s*float|int\(.*strike", l, re.I):
        print(f"  L{i}: {l.strip()[:140]}")
print()
print("=== contract_metadata.py strike handling ===")
for i, l in enumerate(open("src/contract_metadata.py", encoding="utf-8").read().splitlines(), 1):
    if re.search(r"strike|lot|100", l, re.I):
        print(f"  L{i}: {l.strip()[:140]}")
