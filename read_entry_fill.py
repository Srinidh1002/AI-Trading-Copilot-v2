src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
# find "F1 PAPER_FILL" region
for i, l in enumerate(src):
    if "PAPER_FILL" in l or "_bid = float" in l:
        start = max(0, i - 5)
        end = min(len(src), i + 25)
        print(f"=== lines {start+1}-{end} ===")
        for j in range(start, end):
            print(f"{j+1:4d}: {src[j]}")
        print()
        break
