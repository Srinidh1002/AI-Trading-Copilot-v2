import sys
from datetime import datetime
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot
from market_phase import MarketPhaseEngine

# We cannot call is_market_open() with a fake time directly since it uses datetime.now().
# Instead, verify the underlying phase engine produces the expected answers for key times.
eng = MarketPhaseEngine("NIFTY")

test_cases = [
    # (label, year, month, day, hour, minute)
    ("Monday pre-open 09:00", 2026, 9, 15, 9, 0),
    ("Monday 09:15", 2026, 9, 15, 9, 15),
    ("Monday 10:00", 2026, 9, 15, 10, 0),
    ("Monday 14:00", 2026, 9, 15, 14, 0),
    ("Monday 15:14", 2026, 9, 15, 15, 14),
    ("Monday 15:15 (cutoff)", 2026, 9, 15, 15, 15),
    ("Monday 15:27", 2026, 9, 15, 15, 27),
    ("Monday 15:28", 2026, 9, 15, 15, 28),
    ("Monday 15:35", 2026, 9, 15, 15, 35),
    ("Saturday 11:00 (weekend)", 2026, 9, 19, 11, 0),
    ("Sunday 11:00 (weekend)", 2026, 9, 20, 11, 0),
    ("Holiday 2026-10-02 11:00 (Gandhi Jayanti)", 2026, 10, 2, 11, 0),
]

print(f"{'case':<40} {'phase':<20} {'BOT_open?':>10} {'can_enter':>10} {'can_exit':>10}")
print("-" * 90)
for label, y, mo, d, h, mi in test_cases:
    dt = datetime(y, mo, d, h, mi, 0)
    phase, ce, cx, _ = eng.get_phase(dt)
    # Mirror the D1 logic exactly
    bot_open = phase in ("CONTINUOUS", "CLOSE_DRAIN")
    print(f"{label:<40} {phase:<20} {str(bot_open):>10} {str(ce):>10} {str(cx):>10}")
