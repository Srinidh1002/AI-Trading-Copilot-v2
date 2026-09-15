# Same script, SENSEX
with open("n4_bounded_nifty.py", encoding="utf-8") as f:
    src = f.read()
src = src.replace('MARKET = "NIFTY"', 'MARKET = "SENSEX"')
with open("n4_bounded_sensex.py", "w", encoding="utf-8") as f:
    f.write(src)
print("n4_bounded_sensex.py written")
