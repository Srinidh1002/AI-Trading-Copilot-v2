"""
Live Paper Trading - Enhanced with Certification
"""

from services.trading.paper_engine import PaperTradingEngine
import time
import logging
from datetime import datetime, time as dt_time

MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 40

logging.basicConfig(level=logging.INFO)

engine = PaperTradingEngine({
    'mode': 'paper',
    'markets': ['NIFTY', 'SENSEX'],
    'days': 1,
    'max_open_trades': 1,
    'pipeline_config': {
        'min_confidence': 35,
        'min_risk_reward': 0.8,
        'min_technical_score': 30,
        'min_options_score': 30,
    }
})

print("=" * 60)
print("LIVE PAPER TRADING (Enhanced)")
print("PAPER ONLY - NO BROKER ORDERS")
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Market hours: 9:15 AM - 3:30 PM IST")
print("Auto-shutdown at 3:40 PM IST")
print("=" * 60)

def is_market_closed():
    now = datetime.now()
    return now.hour >= MARKET_CLOSE_HOUR and now.minute >= MARKET_CLOSE_MINUTE

cycle = 0
try:
    while True:
        if is_market_closed():
            print(f"\n⏰ Market closed. Shutting down...")
            break
        
        cycle += 1
        print(f"\n🔄 Cycle {cycle}")
        results = engine.run()
        
        # Active trades
        active = engine.get_active_trades()
        if active:
            print(f"\n📊 ACTIVE TRADES:")
            for trade in active:
                print(f"  {trade.market} {trade.direction} @ {trade.entry_price:.2f}")
        
        # Stats
        print(f"\n📈 STATS:")
        for market, stats in results.items():
            trades = stats.get("total_trades", 0)
            if trades > 0:
                print(f"  {market}: {trades} trades")
        
        # Certification
        print(f"\n📋 CERTIFICATION:")
        for market in ["NIFTY", "SENSEX"]:
            stats = engine.certification.get_stats(market)
            if stats:
                progress = f"{stats.countable_trades}/{stats.target_trades}"
                status = "✅" if stats.certification_complete else "⏳"
                print(f"  {status} {market}: {progress}")
        
        time.sleep(5)

except KeyboardInterrupt:
    print("\n🛑 Manual stop.")

print(f"\n🏁 Stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Total cycles: {cycle}")
