from services.market_data import get_chart_data
from services.technical import calculate_indicators
from services.technical_score import technical_score
from services.ai_engine import ai_engine

df = get_chart_data("AAPL")

df = calculate_indicators(df)

technical = technical_score(df)

result = ai_engine(technical)

print(result)