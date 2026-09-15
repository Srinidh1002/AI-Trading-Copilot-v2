import re
src = open("src/target_focused_bot.py", encoding="utf-8").read()
print("=== state file references ===")
for m in re.finditer(r"(_state_file|state_file|nifty_state|nifty_experimental|sensex_state|sensex_experimental)", src):
    line_start = src.rfind("\n", 0, m.start()) + 1
    line_end = src.find("\n", m.end())
    line_no = src[:m.start()].count("\n") + 1
    print(f"L{line_no}: {src[line_start:line_end].strip()}")
