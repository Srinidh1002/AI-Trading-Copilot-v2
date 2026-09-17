from services.market_data import get_chart_data
from services.technical import calculate_indicators
from services.technical_score import technical_score

df = get_chart_data("AAPL")

df = calculate_indicators(df)

result = technical_score(df)

print(result)
