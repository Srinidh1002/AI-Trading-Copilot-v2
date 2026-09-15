from services.market_snapshot import get_market_snapshot

print("=" * 30)
print("MARKET SNAPSHOT TEST")
print("=" * 30)

snapshot = get_market_snapshot()

for key, value in snapshot.items():
    print(f"{key:<20}: {value}")