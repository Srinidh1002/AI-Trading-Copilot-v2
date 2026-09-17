"""D5 — Unify holiday authority: use market_phase.NSE_HOLIDAYS_2026.

Before: inline list at get_expiry() had only 1 holiday (2026-09-14).
After:  authoritative list from market_phase.py (11 holidays for 2026).

Two edits:
  1. Extend import at line 17 to also bring in NSE_HOLIDAYS_2026
  2. Replace inline list with parsed set
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D5_holiday_authority" in src:
    print("D5 already applied")
    raise SystemExit(0)

# 1. Extend the existing market_phase import
old_imp = "from market_phase import MarketPhaseEngine"
new_imp = ("from market_phase import MarketPhaseEngine, NSE_HOLIDAYS_2026  # D5_holiday_authority")
if old_imp not in src:
    raise SystemExit("D5: market_phase import anchor not found")
src = src.replace(old_imp, new_imp, 1)

# 2. Insert a module-level parsed set right after the existing imports block.
# Anchor on the SensitiveFilter usage line which is near the end of imports.
anchor_after_imports = "for _h in logging.getLogger().handlers:"
if anchor_after_imports not in src:
    raise SystemExit("D5: logging handlers anchor not found")
# We insert BEFORE that line — need the line just above it
# Actually safer: use the _sf filter line as anchor
anchor_sf = "_sf = SensitiveFilter(_sensitive)"
if anchor_sf not in src:
    raise SystemExit("D5: SensitiveFilter init anchor not found")
parsed = anchor_sf + '''

# D5_holiday_authority — single source of truth from market_phase.py
_NSE_HOLIDAY_DATES = frozenset(
    datetime.strptime(d, "%Y-%m-%d").date() for d in NSE_HOLIDAYS_2026
)'''
src = src.replace(anchor_sf, parsed, 1)

# 3. Replace the inline list inside trading_days_between
old_fn = '''        # Holiday-aware trading days calculator
        def trading_days_between(start_date, end_date):
            # NSE holidays for Sept 2026 (add more as known)
            holidays = [
                datetime(2026, 9, 14).date(),  # Ganesh Chaturthi
            ]
            count = 0'''
new_fn = '''        # Holiday-aware trading days calculator (D5_holiday_authority)
        def trading_days_between(start_date, end_date):
            holidays = _NSE_HOLIDAY_DATES
            count = 0'''
if old_fn not in src:
    raise SystemExit("D5: trading_days_between anchor not found")
src = src.replace(old_fn, new_fn, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D5: holiday authority unified")
