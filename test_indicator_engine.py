from services.live_multi_timeframe_data import LiveMultiTimeframeData
from services.indicator_engine import calculate_indicators

service = LiveMultiTimeframeData()

df = service.fetch_timeframe(
    exchange="NSE",
    symboltoken="99926000",
    timeframe="5m",
)

indicators = calculate_indicators(df)

print(indicators)