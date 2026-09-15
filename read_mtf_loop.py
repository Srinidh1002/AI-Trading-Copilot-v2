src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
# Show lines 1025-1060 (MTF loop)
for i in range(1024, min(1065, len(src))):
    print(f"{i+1:4d}: {src[i]}")
