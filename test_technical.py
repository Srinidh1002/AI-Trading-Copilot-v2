from services.market_data import get_chart_data
from services.technical import calculate_indicators

df = get_chart_data("AAPL")

df = calculate_indicators(df)

print(df.columns)

print(df.tail())
