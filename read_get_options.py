src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
start = None
for i, l in enumerate(src):
    if "def get_options" in l:
        start = i
        break
if start is not None:
    for j in range(start, min(start + 70, len(src))):
        print(f"{j+1:4d}: {src[j]}")
