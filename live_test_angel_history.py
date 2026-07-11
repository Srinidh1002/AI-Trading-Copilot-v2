from services.broker.angel_client import AngelMarketDataClient


client = AngelMarketDataClient()

print("Logging into Angel One...")
client.login()

print("Fetching NIFTY historical candles...")

response = client.get_historical_data(
    exchange="NSE",
    symboltoken="99926000",
    interval="FIVE_MINUTE",
    fromdate="2026-07-10 09:15",
    todate="2026-07-10 15:30",
)

candles = response.get("data", [])

print(f"\nCandles received: {len(candles)}")

for candle in candles[:5]:
    print(candle)