"""
Live Paper Trading - Lowered Threshold
PAPER ONLY - NO BROKER ORDERS
"""

from services.trading.paper_engine import PaperTradingEngine
import time
import logging

logging.basicConfig(level=logging.INFO)

engine = PaperTradingEngine({
    'mode': 'paper',
    'markets': ['NIFTY', 'SENSEX'],
    'days': 1,
    'max_open_trades': 1,
    'pipeline_config': {
        'min_confidence': 35,        # Lowered from 50
        'min_risk_reward': 0.8,      # Lowered from 1.0
        'min_technical_score': 30,   # Lowered from 40
        'min_options_score': 30,     # Lowered from 40
    }
})

print("=" * 60)
print("LIVE PAPER TRADING (Lowered Threshold)")
print("PAPER ONLY - NO BROKER ORDERS")
print(f"Started at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Market hours: 9:15 AM - 3:30 PM IST")
print("=" * 60)

cycle = 0
while True:
    cycle += 1
    print(f"\nCycle {cycle} - Running live analysis...")
    results = engine.run()
    
    for market, stats in results.items():
        trades = stats.get("total_trades", 0)
        if trades > 0:
            print(f"  ✅ {market}: {trades} new trades")
            print(f"     Wins: {stats.get('wins', 0)}")
            print(f"     Losses: {stats.get('losses', 0)}")
            print(f"     Win Rate: {stats.get('win_rate', 0):.2f}%")
        else:
            print(f"  ⏸️  {market}: 0 trades (confidence below threshold)")
    
    time.sleep(5)
