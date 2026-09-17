"""N4 - bounded paper smoke (production path, bounded cycles, no state corruption)."""
import sys, time
sys.path.append("src")
from datetime import datetime
from target_focused_bot import UnifiedTradingBot

MARKET = "SENSEX"     # change to SENSEX for second run
MAX_CYCLES = 8

bot = UnifiedTradingBot(MARKET)
bot.load_state()
bot.connect_with_retry()
bot.load_instruments()

print(f"Market open: {bot.is_market_open()}")
print(f"Starting {MARKET} progress: {bot.current_session}/100")
print(f"Running {MAX_CYCLES} cycles (bounded)")
print()

cycle_stats = {"ran": 0, "trade": 0, "skip": 0, "err": 0}
for i in range(MAX_CYCLES):
    if not bot.is_market_open():
        print("Market closed - stopping early")
        break
    print(f"\n{'='*60}")
    print(f"Cycle {i+1}/{MAX_CYCLES}  {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    cycle_stats["ran"] += 1
    try:
        result = bot.run_single_session()
        if result:
            bot.current_session += 1
            bot.session_history.append(result)
            bot.sessions_completed_today += 1
            cycle_stats["trade"] += 1
            print(f">>> TRADE - Progress: {bot.current_session}/100")
        else:
            cycle_stats["skip"] += 1
            print(">>> SKIPPED")
    except Exception as e:
        cycle_stats["err"] += 1
        print(f">>> CYCLE ERROR: {str(e)[:120]}")
    bot.save_state()
    if i < MAX_CYCLES - 1 and bot.is_market_open():
        time.sleep(30)

print()
print("=" * 60)
print(f"N4 BOUNDED SMOKE COMPLETE - {MARKET}")
print("=" * 60)
print(f"  cycles run    : {cycle_stats['ran']}")
print(f"  trades fired  : {cycle_stats['trade']}")
print(f"  skipped       : {cycle_stats['skip']}")
print(f"  errors        : {cycle_stats['err']}")
print(f"  counter       : {bot.current_session}/100")
