"""Patch N1-D1 — Wire is_market_open() through MarketPhaseEngine.
BEFORE: uses wall clock only (no weekend/holiday check).
AFTER:  delegates to MarketPhaseEngine which owns the calendar authority.
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "N1_D1_market_phase" in src:
    print("N1-D1 already applied")
    raise SystemExit(0)

# 1. Construct the phase engine in __init__ (find where capital_engine is set)
anchor_init = "        self.capital_engine = CapitalEngine(deployable_capital=100000)"
if anchor_init not in src:
    raise SystemExit("N1-D1: capital_engine init anchor not found")
new_init = anchor_init + '''
        # N1_D1_market_phase — calendar/session authority
        from market_phase import MarketPhaseEngine as _MPE
        self.phase_engine = _MPE(self.market)'''
src = src.replace(anchor_init, new_init, 1)

# 2. Replace is_market_open body
old_fn = '''    def is_market_open(self):
        now = datetime.now()
        return self.MARKET_OPEN <= now <= self.FINAL_EXIT'''
new_fn = '''    def is_market_open(self):
        """N1_D1_market_phase — delegate to MarketPhaseEngine (calendar authority).
        Falls back to wall-clock only if phase_engine is unavailable (defensive)."""
        try:
            return self.phase_engine.is_market_open()
        except AttributeError:
            now = datetime.now()
            return self.MARKET_OPEN <= now <= self.FINAL_EXIT'''
if old_fn not in src:
    raise SystemExit("N1-D1: is_market_open anchor not found")
src = src.replace(old_fn, new_fn, 1)

# 3. Also add can_enter() as a public method (needed for N3C)
anchor_can = new_fn
add_can = anchor_can + '''

    def can_enter(self):
        """N1_D1_market_phase — entry permission per session phase."""
        try:
            return self.phase_engine.can_enter()
        except AttributeError:
            return self.is_market_open()

    def session_note(self):
        """N1_D1_market_phase — human-readable phase for logs."""
        try:
            return self.phase_engine.describe().get("note", "")
        except AttributeError:
            return ""'''
src = src.replace(anchor_can, add_can, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("N1-D1: is_market_open() now delegates to MarketPhaseEngine")
