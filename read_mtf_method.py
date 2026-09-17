src = open("src/market_intelligence.py", encoding="utf-8").read().splitlines()
for i, l in enumerate(src):
    if "def get_multi_timeframe_technicals" in l:
        for j in range(i, min(i + 80, len(src))):
            print(f"{j+1:4d}: {src[j]}")
        break
