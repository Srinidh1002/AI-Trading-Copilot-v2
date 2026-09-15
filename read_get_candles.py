# Show market_intelligence.get_candles method
src = open("src/market_intelligence.py", encoding="utf-8").read().splitlines()
for i, l in enumerate(src):
    if "def get_candles" in l:
        start = i
        end = min(i + 60, len(src))
        for j in range(start, end):
            print(f"{j+1:4d}: {src[j]}")
        break
