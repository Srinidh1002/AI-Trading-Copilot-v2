src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
# find the line containing trading_days_between
for i, l in enumerate(src):
    if "trading_days_between" in l:
        start = max(0, i - 5)
        end = min(len(src), i + 15)
        print(f"=== lines {start+1}-{end} ===")
        for j in range(start, end):
            print(f"{j+1:4d}: {src[j]}")
        break
