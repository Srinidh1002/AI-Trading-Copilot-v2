src = open("src/mtf_enhanced.py", encoding="utf-8").read().splitlines()
print(f"Total lines: {len(src)}")
for i, l in enumerate(src):
    if "def compute_indicators" in l or "def timeframe_decision" in l:
        print(f"=== {l.strip()} (L{i+1}) ===")
        for j in range(i, min(i + 50, len(src))):
            print(f"{j+1:4d}: {src[j]}")
        print()
