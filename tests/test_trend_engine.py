from services.market_snapshot import get_market_snapshot
from services.trend_engine import analyze_trend

snapshot = get_market_snapshot()

print("SNAPSHOT:")
print(snapshot)

print("\nINDICATORS:")
print(snapshot["indicators"])

trend = analyze_trend(snapshot)

print("\nTREND:")
print(trend)