src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
# find select_trade def
start = None
for i, l in enumerate(src):
    if "def select_trade" in l:
        start = i
        break
if start is not None:
    for j in range(start, min(start + 80, len(src))):
        print(f"{j+1:4d}: {src[j]}")
