src = open("src/market_intelligence.py", encoding="utf-8").read().splitlines()
# show _fresh, _store, _recently_failed, _mark_failed, __init__
for name in ("def __init__", "def _fresh", "def _store", "def _recently_failed", "def _mark_failed"):
    for i, l in enumerate(src):
        if name in l:
            print(f"=== {name} (L{i+1}) ===")
            for j in range(i, min(i + 15, len(src))):
                print(f"{j+1:4d}: {src[j]}")
            print()
            break
