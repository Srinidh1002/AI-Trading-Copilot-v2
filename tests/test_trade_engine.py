from services.market_snapshot import get_market_snapshot
from services.trade_engine import analyze_trade

print("=" * 20)
print("TRADE ENGINE TEST")
print("=" * 20)

snapshot = get_market_snapshot()

result = analyze_trade(snapshot)

print(result)