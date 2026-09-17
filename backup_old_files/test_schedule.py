# test_schedule.py
# Test the market schedule logic

from run_trading_with_scheduler import MarketSchedule
from datetime import datetime
import pytz

print("=" * 60)
print("📋 Market Schedule Test")
print("=" * 60)

ist = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist)

print(f"\n📍 Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📍 Current Time: {now.time()}")

print(f"\n📊 Market Status:")
print(f"  Pre-market: {MarketSchedule.is_pre_market()}")
print(f"  Market Open: {MarketSchedule.is_market_open()}")
print(f"  Should Shutdown: {MarketSchedule.should_shutdown()}")

print(f"\n⏰ Time until trading start: {MarketSchedule.time_until_trading_start()}")
print(f"⏰ Time until shutdown: {MarketSchedule.time_until_shutdown()}")

print(f"\n📋 Schedule:")
print(f"  Pre-market starts: 9:00 AM")
print(f"  Trading starts: 9:15 AM")
print(f"  Trading ends: 3:30 PM")
print(f"  Peaceful shutdown: 3:40 PM")
