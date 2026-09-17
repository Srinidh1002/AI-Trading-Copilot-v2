from services.market_snapshot import get_market_snapshot

print("=" * 20)
print("ATR TEST")
print("=" * 20)

snapshot = get_market_snapshot()

print(snapshot["indicators"])