from services.market_data import get_stock_data, get_chart_data

print(get_stock_data("AAPL"))

df = get_chart_data("AAPL")

print(df.tail())
