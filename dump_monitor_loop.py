src = open("src/target_focused_bot.py", encoding="utf-8").read().splitlines()
print("=== lines 1545-1680 (monitor loop) ===")
for i in range(1544, min(1680, len(src))):
    print(f"{i+1:4d}: {src[i]}")
