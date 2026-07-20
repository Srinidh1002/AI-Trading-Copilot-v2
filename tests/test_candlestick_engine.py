"""
Candlestick Engine Test
"""

from services.market_data import get_historical_data
from services.candlestick_engine import detect_pattern


print("=" * 30)
print("CANDLESTICK ENGINE TEST")
print("=" * 30)

df = get_historical_data()

result = detect_pattern(df)

print()
print("Detected Pattern")
print("----------------")
print(result)