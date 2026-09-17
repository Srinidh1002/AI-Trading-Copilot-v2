import sys
sys.path.append("src")
from target_focused_bot import _NSE_HOLIDAY_DATES
from market_phase import NSE_HOLIDAYS_2026

print(f"Source: {len(NSE_HOLIDAYS_2026)} ISO strings")
print(f"Parsed: {len(_NSE_HOLIDAY_DATES)} date objects")
assert len(_NSE_HOLIDAY_DATES) == len(NSE_HOLIDAYS_2026), "count mismatch"

# Every 2026 date in the set must be a valid parsed ISO date
from datetime import date
assert all(isinstance(d, date) for d in _NSE_HOLIDAY_DATES)
assert all(d.year == 2026 for d in _NSE_HOLIDAY_DATES)

# Spot-check Ganesh Chaturthi (Sept 14)
assert date(2026, 9, 14) in _NSE_HOLIDAY_DATES
# Spot-check one older holiday that was NOT in the old inline list
assert date(2026, 1, 26) in _NSE_HOLIDAY_DATES  # Republic Day

print("D5 verification PASSED")
