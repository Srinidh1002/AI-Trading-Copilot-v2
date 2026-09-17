import re
src = open("src/target_focused_bot.py", encoding="utf-8").read()
# grep for bid-related method calls anywhere
for m in re.finditer(r'\.(get_bid|bidData|getMarketData|fullQuote|marketData|optionChain|ltpData)\s*\(', src):
    start = src.rfind("\n", 0, m.start()) + 1
    end = src.find("\n", m.end())
    line_no = src[:m.start()].count("\n") + 1
    print(f"L{line_no}: {src[start:end].strip()}")
