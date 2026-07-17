from services.broker.angel_client import AngelMarketDataClient
import traceback

client = AngelMarketDataClient()

print("=" * 70)
print("ANGEL ONE HISTORICAL DATA TEST")
print("=" * 70)

try:
    print("\nLogging into Angel One...")
    client.login()
    print("✓ Login successful")

    print("\nRequesting ONE DAY of 5-minute NIFTY candles...")
    print("Exchange   : NSE")
    print("Token      : 99926000")
    print("Interval   : FIVE_MINUTE")
    print("From       : 2026-07-10 09:15")
    print("To         : 2026-07-10 15:30")
    print("-" * 70)

    response = client.get_historical_data(
        exchange="NSE",
        symboltoken="99926000",
        interval="FIVE_MINUTE",
        fromdate="2026-07-10 09:15",
        todate="2026-07-10 15:30",
    )

    candles = response.get("data", [])

    print("\n✓ REQUEST SUCCEEDED")
    print(f"Candles received: {len(candles)}")

    if candles:
        print("\nFirst candle:")
        print(candles[0])

        print("\nLast candle:")
        print(candles[-1])

except Exception as e:
    print("\n✗ REQUEST FAILED")
    print(type(e).__name__)
    print(e)

    print("\nFull traceback:")
    traceback.print_exc()

print("\n" + "=" * 70)
