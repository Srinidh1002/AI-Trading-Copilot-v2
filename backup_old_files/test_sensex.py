"""
Quick fix for SENSEX trading
"""
from services.trading.paper_engine import PaperTradingEngine

# Run SENSEX with explicit config
engine = PaperTradingEngine({
    "mode": "replay",
    "markets": ["SENSEX"],
    "days": 5,
    "max_open_trades": 1
})

print("Running SENSEX test...")
results = engine.run()

for market, stats in results.items():
    print(f"\n{market}:")
    print(f"  Trades: {stats.get('total_trades', 0)}")
    print(f"  Wins: {stats.get('wins', 0)}")
    print(f"  Losses: {stats.get('losses', 0)}")
    print(f"  Win Rate: {stats.get('win_rate', 0):.2f}%")
