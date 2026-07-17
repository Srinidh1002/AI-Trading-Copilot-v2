from services.market_snapshot import get_market_snapshot

snapshot = get_market_snapshot()

print("\n====================")
print("ADX TEST")
print("====================")

print(snapshot["indicators"])