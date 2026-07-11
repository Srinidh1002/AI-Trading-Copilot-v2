from services.broker.angel_client import AngelMarketDataClient


client = AngelMarketDataClient()

print("Logging into Angel One...")
login_response = client.login()

print("Login successful:", login_response["status"])

print("\nFetching live NIFTY market data...")

market_data = client.get_market_data(
    mode="FULL",
    exchange_tokens={
        "NSE": ["99926000"]
    },
)

print("\nLIVE MARKET DATA:")
print(market_data)