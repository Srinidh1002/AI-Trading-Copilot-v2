"""D1 — is_market_open() delegates to MarketPhaseEngine (weekend/holiday aware).

Before: wall-clock only. Weekends/holidays returned True for 6h13m.
After:  phase engine decides. True only during CONTINUOUS or CLOSE_DRAIN.
        False on weekends, holidays, and after 15:28. Fallback preserved
        if phase engine is unavailable (defensive).
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D1_market_phase" in src:
    print("D1 already applied")
    raise SystemExit(0)

old = '''    def is_market_open(self):
        now = datetime.now()
        return self.MARKET_OPEN <= now <= self.FINAL_EXIT'''
new = '''    def is_market_open(self):
        """D1_market_phase — delegate to MarketPhaseEngine.
        True during CONTINUOUS (09:15-15:15) and CLOSE_DRAIN (15:15-15:28).
        False on weekends, holidays, and after 15:28."""
        try:
            phase, _, _, _ = self.market_phase.get_phase()
            return phase in ("CONTINUOUS", "CLOSE_DRAIN")
        except AttributeError:
            now = datetime.now()
            return self.MARKET_OPEN <= now <= self.FINAL_EXIT'''

if old not in src:
    raise SystemExit("D1 anchor not found")
src = src.replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D1: is_market_open delegates to MarketPhaseEngine")
