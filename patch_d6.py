"""D6 - Tick-align paper fills to 0.05 (options grid).

Before: round(fill, 2) produced non-tradeable prices like 175.26
After:  round to nearest 0.05 tick
"""
path = "src/capital_engine.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D6_tick_align" in src:
    print("D6 already applied")
    raise SystemExit(0)

# 1. Add tick size constant at top of class
old_class = """class CapitalEngine:
    def __init__(self, deployable_capital=100000,"""
new_class = """class CapitalEngine:
    # D6_tick_align - options trade on a 0.05 grid on NSE/BSE F&O
    OPTION_TICK = 0.05

    def __init__(self, deployable_capital=100000,"""
if old_class not in src:
    raise SystemExit("D6: class anchor not found")
src = src.replace(old_class, new_class, 1)

# 2. Add static helper method
anchor = """        self.slippage_pct = slippage_pct
    
    def compute_lot_size(self, premium, lot_size):"""
new_anchor = """        self.slippage_pct = slippage_pct

    @staticmethod
    def _round_to_tick(price, tick=None):
        \"\"\"D6_tick_align - round to nearest valid tick (0.05 default).\"\"\"
        if price is None:
            return None
        t = tick if tick is not None else CapitalEngine.OPTION_TICK
        if t <= 0:
            return round(price, 2)
        return round(round(price / t) * t, 2)

    def compute_lot_size(self, premium, lot_size):"""
if anchor not in src:
    raise SystemExit("D6: helper anchor not found")
src = src.replace(anchor, new_anchor, 1)

# 3. Apply tick round in compute_paper_fill return
old_fill = """        slippage = base * (self.slippage_pct / 100)
        fill = base + slippage if direction == "BUY" else base - slippage
        return (round(fill, 2), "OK")"""
new_fill = """        slippage = base * (self.slippage_pct / 100)
        fill = base + slippage if direction == "BUY" else base - slippage
        # D6_tick_align - round to 0.05 grid
        return (self._round_to_tick(fill), "OK")"""
if old_fill not in src:
    raise SystemExit("D6: fill return anchor not found")
src = src.replace(old_fill, new_fill, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D6: paper fills tick-aligned to 0.05")
